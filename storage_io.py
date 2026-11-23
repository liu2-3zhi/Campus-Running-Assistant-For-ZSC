"""Module-local compatibility I/O over database-backed business entities.

Only paths accepted by StoragePolicy are redirected. Import these names in a
business module; standard library modules and builtins are never patched.
"""
from __future__ import annotations

import builtins as _builtins
import configparser as _configparser
import fnmatch as _fnmatch
import glob as _glob
import io as _io
import os as _os
import shutil as _shutil
import stat as _stat


def get_runtime(*paths):
    from business_storage import get_runtime as runtime_factory, get_runtime_for_paths
    return get_runtime_for_paths(*paths) if paths else runtime_factory()


def _runtime(*paths):
    runtime = get_runtime(*paths)
    if runtime is None:
        return None
    if runtime.backend not in {"sqlite", "mysql"}:
        from business_storage import StorageConfigurationError
        raise StorageConfigurationError('The file storage backend is frozen; use sqlite or mysql')
    return runtime


def is_managed_path(path):
    """Report whether a compatibility path belongs to database storage."""
    return _identify(path) is not None


def _identify(path, runtime=None):
    if isinstance(path, int):
        return None
    runtime = runtime if runtime is not None else _runtime(path)
    return runtime.policy.identify(path) if runtime is not None else None


def _directory(path, runtime=None):
    if isinstance(path, int):
        return None
    runtime = runtime if runtime is not None else _runtime(path)
    return runtime.policy.directory(path) if runtime is not None else None


def _prefix(value):
    value = value.replace("\\", "/").strip("/")
    return value + "/" if value else ""


def _missing(path):
    return FileNotFoundError(2, "No such file or directory", _os.fspath(path))


class _ManagedFile:
    def __init__(self, runtime, identity, path, mode, buffering, encoding, errors, newline):
        if not isinstance(mode, str):
            raise TypeError("mode must be a string")
        if (not mode or any(character not in "rwaxbt+" for character in mode)
                or any(mode.count(character) > 1 for character in mode)
                or sum(mode.count(character) for character in "rwax") != 1
                or ("b" in mode and "t" in mode)):
            raise ValueError(f"invalid mode: {mode!r}")
        binary = "b" in mode
        operation = next(character for character in mode if character in "rwax")
        if binary and (encoding is not None or errors is not None or newline is not None):
            raise ValueError("binary mode doesn't take an encoding, errors or newline argument")
        if not binary and buffering == 0:
            raise ValueError("can't have unbuffered text I/O")
        self.name, self.mode = _os.fspath(path), mode
        self._runtime, self._identity = runtime, identity
        self._document = runtime.store.get(*identity)
        self._readable = operation == "r" or "+" in mode
        self._writable = operation in "wax" or "+" in mode
        self._append = operation == "a"
        self._create_only = operation == "x"
        self._closed = False
        if operation == "r" and self._document is None:
            raise _missing(path)
        if self._create_only and self._document is not None:
            raise FileExistsError(17, "File exists", self.name)
        content = self._document.content if self._document is not None and operation not in "wx" else b""
        self._committed = content
        self._must_commit = operation in "wx" or (self._append and self._document is None)
        self._raw = _io.BytesIO(content)
        self._stream = self._raw if binary else _io.TextIOWrapper(
            self._raw, encoding=encoding, errors=errors, newline=newline,
            line_buffering=buffering == 1,
        )
        if self._append:
            self._stream.seek(0, _os.SEEK_END)

    def __enter__(self):
        self._check_closed()
        return self

    def __exit__(self, exception_type, exception, traceback):
        self._finish(commit=exception_type is None)
        return False

    def __iter__(self):
        self._check_readable()
        return self

    def __next__(self):
        line = self.readline()
        if line == b"" or line == "":
            raise StopIteration
        return line

    def __getattr__(self, name):
        return getattr(self._stream, name)

    @property
    def closed(self):
        return self._closed

    def _check_closed(self):
        if self.closed:
            raise ValueError("I/O operation on closed file")

    def _check_readable(self):
        self._check_closed()
        if not self._readable:
            raise _io.UnsupportedOperation("not readable")

    def _check_writable(self):
        self._check_closed()
        if not self._writable:
            raise _io.UnsupportedOperation("not writable")

    def read(self, size=-1):
        self._check_readable()
        return self._stream.read(size)

    def readline(self, size=-1):
        self._check_readable()
        return self._stream.readline(size)

    def readlines(self, hint=-1):
        self._check_readable()
        return self._stream.readlines(hint)

    def readinto(self, buffer):
        self._check_readable()
        return self._stream.readinto(buffer)

    def write(self, content):
        self._check_writable()
        if self._append:
            self._stream.seek(0, _os.SEEK_END)
        return self._stream.write(content)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def truncate(self, size=None):
        self._check_writable()
        return self._stream.truncate(size)

    def readable(self):
        self._check_closed()
        return self._readable

    def writable(self):
        self._check_closed()
        return self._writable

    def seekable(self):
        self._check_closed()
        return True

    def fileno(self):
        raise _io.UnsupportedOperation("database documents have no file descriptor")

    def flush(self):
        self._check_closed()
        self._stream.flush()
        if not self._writable:
            return
        content = self._raw.getvalue()
        if not self._must_commit and content == self._committed:
            return
        kwargs = {"create_only": self._create_only}
        if not self._create_only:
            kwargs["expected_revision"] = self._document.revision if self._document is not None else 0
        self._document = self._runtime.store.put(*self._identity, content, **kwargs)
        self._committed, self._must_commit, self._create_only = content, False, False

    def _finish(self, commit):
        if self.closed:
            return
        try:
            if commit:
                self.flush()
        finally:
            self._closed = True
            self._stream.close()

    def close(self):
        self._finish(commit=True)


def open(file, mode="r", buffering=-1, encoding=None, errors=None, newline=None,
         closefd=True, opener=None):
    runtime = _runtime(file)
    identity = _identify(file, runtime) if runtime is not None else None
    if identity is None:
        return _builtins.open(file, mode, buffering, encoding, errors, newline, closefd, opener)
    if not closefd:
        raise ValueError("Cannot use closefd=False with file name")
    if opener is not None:
        raise ValueError("custom openers cannot operate on database documents")
    return _ManagedFile(runtime, identity, file, mode, buffering, encoding, errors, newline)


def _directory_documents(runtime, identity):
    namespace, prefix = identity
    prefix = _prefix(prefix)
    return prefix, [document for document in runtime.store.list(namespace, prefix)
                    if document.key.startswith(prefix)]


class _PathProxy:
    def __getattr__(self, name):
        return getattr(_os.path, name)

    def exists(self, path):
        runtime = _runtime(path)
        identity = _identify(path, runtime) if runtime is not None else None
        if identity is not None:
            return runtime.store.get(*identity) is not None
        if _os.path.exists(path):
            return True
        return self.isdir(path) if _directory(path, runtime) is not None else False

    def lexists(self, path):
        runtime = _runtime(path)
        if runtime is not None and (_identify(path, runtime) is not None or _directory(path, runtime) is not None):
            return self.exists(path)
        return _os.path.lexists(path)

    def isfile(self, path):
        runtime = _runtime(path)
        identity = _identify(path, runtime) if runtime is not None else None
        if identity is not None:
            return runtime.store.get(*identity) is not None
        return _os.path.isfile(path)

    def isdir(self, path):
        runtime = _runtime(path)
        identity = _directory(path, runtime) if runtime is not None else None
        if identity is not None:
            prefix, documents = _directory_documents(runtime, identity)
            return not prefix or bool(documents) or _os.path.isdir(path)
        return _os.path.isdir(path)

    def getsize(self, path):
        return os.stat(path).st_size

    def getmtime(self, path):
        return os.stat(path).st_mtime

    def getctime(self, path):
        return os.stat(path).st_ctime


class _OSProxy:
    path = _PathProxy()

    def __getattr__(self, name):
        return getattr(_os, name)

    def stat(self, path, *, dir_fd=None, follow_symlinks=True):
        runtime = _runtime(path) if dir_fd is None else None
        identity = _identify(path, runtime) if runtime is not None and dir_fd is None else None
        if identity is not None:
            document = runtime.store.get(*identity)
            if document is None:
                raise _missing(path)
            size, mtime_ns, kind = len(document.content), document.mtime_ns, _stat.S_IFREG
        elif runtime is not None and dir_fd is None and _directory(path, runtime) is not None and self.path.isdir(path):
            if _os.path.isdir(path):
                return _os.stat(path, follow_symlinks=follow_symlinks)
            _, documents = _directory_documents(runtime, _directory(path, runtime))
            size, mtime_ns, kind = 0, max((item.mtime_ns for item in documents), default=0), _stat.S_IFDIR
        else:
            return _os.stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)
        stamp = mtime_ns / 1_000_000_000
        return _os.stat_result((kind | 0o600, 0, 0, 1, 0, 0, size, stamp, stamp, stamp),
                               {"st_atime_ns": mtime_ns, "st_mtime_ns": mtime_ns, "st_ctime_ns": mtime_ns})

    def listdir(self, path="."):
        runtime = _runtime(path)
        identity = _directory(path, runtime) if runtime is not None else None
        if identity is None:
            return _os.listdir(path)
        if not self.path.isdir(path):
            raise _missing(path)
        binary = isinstance(_os.fspath(path), bytes)
        plain_path = _os.fsdecode(path)
        names = set()
        if _os.path.isdir(path):
            for name in _os.listdir(plain_path):
                if runtime.policy.identify(_os.path.join(plain_path, name)) is None:
                    names.add(name)
        prefix, documents = _directory_documents(runtime, identity)
        for document in documents:
            remaining = document.key[len(prefix):]
            if remaining:
                names.add(remaining.split("/", 1)[0])
        return [_os.fsencode(name) if binary else name for name in sorted(names)]

    def remove(self, path, *, dir_fd=None):
        runtime = _runtime(path) if dir_fd is None else None
        identity = _identify(path, runtime) if runtime is not None and dir_fd is None else None
        if identity is None:
            return _os.remove(path, dir_fd=dir_fd)
        document = runtime.store.get(*identity)
        if document is None:
            raise _missing(path)
        return runtime.store.delete(*identity, expected_revision=document.revision)

    unlink = remove

    def makedirs(self, name, mode=0o777, exist_ok=False):
        return _os.makedirs(name, mode=mode, exist_ok=exist_ok)

    def replace(self, source, destination, *, src_dir_fd=None, dst_dir_fd=None):
        runtime = _runtime(source, destination)
        source_id = _identify(source, runtime) if runtime is not None and src_dir_fd is None else None
        target_id = _identify(destination, runtime) if runtime is not None and dst_dir_fd is None else None
        if source_id is None and target_id is None:
            return _os.replace(source, destination, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)
        if src_dir_fd is not None or dst_dir_fd is not None:
            raise ValueError("dir_fd cannot cross the database boundary")
        if source_id is not None:
            document = runtime.store.get(*source_id)
            if document is None:
                raise _missing(source)
            content, mtime_ns = document.content, document.mtime_ns
        else:
            with _builtins.open(source, "rb") as origin:
                content = origin.read()
            mtime_ns = _os.stat(source).st_mtime_ns
        if source_id is not None and source_id == target_id:
            return None
        if target_id is not None:
            with runtime.store.transaction():
                runtime.store.put(*target_id, content, mtime_ns=mtime_ns)
                if source_id is not None:
                    runtime.store.delete(*source_id, expected_revision=document.revision)
            if source_id is None:
                _os.remove(source)
        else:
            # Write the destination first: a failed write must never discard source data.
            with _builtins.open(destination, "wb") as target:
                target.write(content)
            runtime.store.delete(*source_id, expected_revision=document.revision)

    def rename(self, source, destination, *, src_dir_fd=None, dst_dir_fd=None):
        runtime = _runtime(source, destination)
        if runtime is None or (_identify(source, runtime) is None and _identify(destination, runtime) is None):
            return _os.rename(source, destination, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)
        return self.replace(source, destination, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)


os = _OSProxy()


class _GlobProxy:
    def __getattr__(self, name):
        return getattr(_glob, name)

    def glob(self, pathname, *, root_dir=None, dir_fd=None, recursive=False, include_hidden=False):
        return list(self.iglob(pathname, root_dir=root_dir, dir_fd=dir_fd, recursive=recursive, include_hidden=include_hidden))

    def iglob(self, pathname, *, root_dir=None, dir_fd=None, recursive=False, include_hidden=False):
        if dir_fd is not None:
            yield from _glob.iglob(pathname, root_dir=root_dir, dir_fd=dir_fd, recursive=recursive, include_hidden=include_hidden)
            return
        binary = isinstance(_os.fspath(pathname), bytes)
        pattern = _os.fsdecode(pathname)
        if _os.altsep:
            pattern = pattern.replace(_os.altsep, _os.sep)
        drive, tail = _os.path.splitdrive(pattern)
        absolute = tail.startswith(_os.sep)
        trailing = tail.endswith(_os.sep)
        pieces = [part for part in tail.split(_os.sep) if part]
        initial = drive + _os.sep if absolute else _os.fsdecode(root_dir) if root_dir is not None else "."
        anchor = initial
        for part in pieces:
            if _glob.has_magic(part):
                break
            anchor = _os.path.join(anchor, part)
        runtime = _runtime(anchor)
        if (runtime is None or runtime.policy.directory(anchor) is None
                and runtime.policy.identify(anchor) is None):
            yield from _glob.iglob(pathname, root_dir=root_dir, dir_fd=dir_fd, recursive=recursive, include_hidden=include_hidden)
            return
        found = []

        def descendants(current):
            try:
                children = os.listdir(current)
            except OSError:
                return
            for name in children:
                if not include_hidden and name.startswith("."):
                    continue
                child = _os.path.join(current, name)
                yield child
                if os.path.isdir(child):
                    yield from descendants(child)

        def visit(current, index):
            if index == len(pieces):
                if os.path.exists(current) and (not trailing or os.path.isdir(current)):
                    found.append(current)
                return
            part = pieces[index]
            if part == "**" and recursive:
                if index == len(pieces) - 1:
                    found.append(current + _os.sep)
                    found.extend(child for child in descendants(current)
                                 if not trailing or os.path.isdir(child))
                    return
                visit(current, index + 1)
                try:
                    children = os.listdir(current)
                except OSError:
                    return
                for name in children:
                    if not include_hidden and name.startswith("."):
                        continue
                    child = _os.path.join(current, name)
                    if os.path.isdir(child):
                        visit(child, index)
                return
            if not _glob.has_magic(part):
                visit(_os.path.join(current, part), index + 1)
                return
            try:
                children = os.listdir(current)
            except OSError:
                return
            for name in children:
                if not include_hidden and name.startswith(".") and not part.startswith("."):
                    continue
                if _fnmatch.fnmatch(name, part):
                    visit(_os.path.join(current, name), index + 1)

        visit(initial, 0)
        for result in found:
            if not absolute:
                result = _os.path.relpath(result, initial)
            if trailing and not result.endswith(_os.sep):
                result += _os.sep
            yield _os.fsencode(result) if binary else result


glob = _GlobProxy()


class _ShutilProxy:
    def __getattr__(self, name):
        return getattr(_shutil, name)

    def _copy(self, source, destination, preserve, follow_symlinks=True):
        runtime = _runtime(source, destination)
        if os.path.isdir(destination):
            destination = _os.path.join(destination, _os.path.basename(source))
        source_id = _identify(source, runtime) if runtime is not None else None
        target_id = _identify(destination, runtime) if runtime is not None else None
        if source_id is None and target_id is None:
            method = _shutil.copy2 if preserve else _shutil.copy
            return method(source, destination, follow_symlinks=follow_symlinks)
        if source_id == target_id and source_id is not None:
            raise _shutil.SameFileError(source, destination, "are the same document")
        with open(source, "rb") as origin:
            content = origin.read()
        metadata = os.stat(source)
        if target_id is not None:
            runtime.store.put(*target_id, content, mtime_ns=metadata.st_mtime_ns if preserve else None)
        else:
            with _builtins.open(destination, "wb") as target:
                target.write(content)
            if preserve:
                _os.utime(destination, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        return destination

    def copy(self, source, destination, *, follow_symlinks=True):
        return self._copy(source, destination, False, follow_symlinks)

    def copy2(self, source, destination, *, follow_symlinks=True):
        return self._copy(source, destination, True, follow_symlinks)

    def move(self, source, destination, copy_function=None):
        runtime = _runtime(source, destination)
        if runtime is None:
            return _shutil.move(source, destination, copy_function=copy_function or _shutil.copy2)
        if os.path.isdir(destination):
            destination = _os.path.join(destination, _os.path.basename(source))
            if os.path.exists(destination):
                raise _shutil.Error(f"Destination path {destination!r} already exists")
        source_id, target_id = _identify(source, runtime), _identify(destination, runtime)
        if source_id is not None or target_id is not None:
            if copy_function is not None:
                copy_function(source, destination)
                os.remove(source)
            else:
                os.replace(source, destination)
            return destination
        if _directory(source, runtime) is None and _directory(destination, runtime) is None:
            return _shutil.move(source, destination, copy_function=copy_function or _shutil.copy2)
        if not os.path.isdir(source):
            return _shutil.move(source, destination, copy_function=copy_function or _shutil.copy2)
        os.makedirs(destination, exist_ok=True)
        for name in os.listdir(source):
            origin, target = _os.path.join(source, name), _os.path.join(destination, name)
            if os.path.isdir(origin):
                self._copy_tree(origin, target, copy_function or self.copy2)
            else:
                (copy_function or self.copy2)(origin, target)
        self.rmtree(source)
        return destination

    def _copy_tree(self, source, destination, copy_function):
        os.makedirs(destination, exist_ok=True)
        for name in os.listdir(source):
            origin, target = _os.path.join(source, name), _os.path.join(destination, name)
            if os.path.isdir(origin):
                self._copy_tree(origin, target, copy_function)
            else:
                copy_function(origin, target)

    def _remove_physical_assets(self, runtime, path):
        """Remove explicit filesystem assets, preserving managed migration originals."""
        preserved = False
        is_excluded = getattr(runtime.policy, "is_excluded", lambda candidate: False)
        for name in _os.listdir(path):
            child = _os.path.join(path, name)
            if runtime.policy.identify(child) is not None or is_excluded(child):
                preserved = True
            elif _os.path.isdir(child) and not _os.path.islink(child):
                preserved = self._remove_physical_assets(runtime, child) or preserved
            else:
                _os.unlink(child)
        if not preserved:
            _os.rmdir(path)
        return preserved

    def rmtree(self, path, ignore_errors=False, onerror=None, *, dir_fd=None, onexc=None):
        runtime = _runtime(path) if dir_fd is None else None
        identity = _directory(path, runtime) if runtime is not None and dir_fd is None else None
        if identity is None:
            kwargs = {"ignore_errors": ignore_errors, "onerror": onerror, "dir_fd": dir_fd}
            if onexc is not None:
                kwargs["onexc"] = onexc
            return _shutil.rmtree(path, **kwargs)
        try:
            if not os.path.isdir(path):
                raise _missing(path)
            _, documents = _directory_documents(runtime, identity)
            with runtime.store.transaction():
                for document in documents:
                    runtime.store.delete(document.namespace, document.key, expected_revision=document.revision)
            if _os.path.exists(path):
                self._remove_physical_assets(runtime, path)
        except Exception as exception:
            if ignore_errors:
                return
            if onexc is not None:
                onexc(self.rmtree, path, exception)
            elif onerror is not None:
                import sys
                onerror(self.rmtree, path, sys.exc_info())
            else:
                raise


shutil = _ShutilProxy()


class RawConfigParser(_configparser.RawConfigParser):
    def read(self, filenames, encoding=None):
        if isinstance(filenames, (str, bytes, _os.PathLike)):
            filenames = [filenames]
        loaded = []
        for filename in filenames:
            filename = _os.fspath(filename)
            try:
                with open(filename, encoding=encoding) as source:
                    self._read(source, filename)
            except OSError:
                continue
            loaded.append(filename)
        return loaded


class ConfigParser(RawConfigParser, _configparser.ConfigParser):
    pass


class _ConfigParserProxy:
    RawConfigParser = RawConfigParser
    ConfigParser = ConfigParser

    def __getattr__(self, name):
        return getattr(_configparser, name)


configparser = _ConfigParserProxy()
