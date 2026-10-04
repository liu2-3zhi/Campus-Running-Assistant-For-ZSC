from __future__ import annotations


from main_runtime import _main


def _decode_frontend_javascript_content(content):
    if isinstance(content, bytes):
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("latin-1", errors="replace")
    return str(content or "")


def _javascript_identifier_char(char):
    return bool(char) and (char.isalnum() or char in ("_", "$"))


def _javascript_previous_nonspace_and_identifier(output_chars):
    previous = ""
    identifier_reversed = []
    for chunk in reversed(output_chars):
        for char in reversed(chunk):
            if not previous:
                if char.isspace():
                    continue
                previous = char
                if not _javascript_identifier_char(char):
                    return previous, ""
                identifier_reversed.append(char)
                continue
            if _javascript_identifier_char(char):
                identifier_reversed.append(char)
                continue
            return previous, "".join(reversed(identifier_reversed))
    return previous, "".join(reversed(identifier_reversed))


def _javascript_previous_token_allows_regex(output_chars):
    last_char, previous_identifier = _javascript_previous_nonspace_and_identifier(
        output_chars
    )
    if not last_char:
        return True
    if last_char in "({[=,:;!&|?+-*~%^<>":
        return True
    return previous_identifier in {
        "return",
        "throw",
        "case",
        "delete",
        "void",
        "typeof",
        "instanceof",
        "in",
        "of",
        "yield",
        "await",
        "else",
        "do",
        "new",
    }


def _copy_javascript_string_literal(source, index, quote):
    result = [quote]
    index += 1
    escaped = False
    while index < len(source):
        char = source[index]
        result.append(char)
        index += 1
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == quote:
            break
    return "".join(result), index


def _copy_javascript_template_expression(
    source,
    index,
    compact_interpolations=False,
):
    output = []
    brace_depth = 1
    while index < len(source):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""
        if char in ("'", '"'):
            literal, index = _copy_javascript_string_literal(source, index, char)
            output.append(literal)
            continue
        if char == "`":
            literal, index = _copy_javascript_template_literal(
                source,
                index,
                compact_interpolations=compact_interpolations,
            )
            output.append(literal)
            continue
        if char == "/" and next_char == "/":
            index += 2
            while index < len(source) and source[index] not in "\r\n":
                index += 1
            output.append("\n")
            continue
        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < len(source) and not (
                source[index] == "*" and source[index + 1] == "/"
            ):
                index += 1
            index = min(index + 2, len(source))
            output.append(" ")
            continue
        if char == "/" and _javascript_previous_token_allows_regex(output):
            literal, index = _copy_javascript_regex_literal(source, index)
            output.append(literal)
            continue
        if char == "{":
            brace_depth += 1
            output.append(char)
            index += 1
            continue
        if char == "}":
            if brace_depth == 1:
                break
            brace_depth -= 1
        output.append(char)
        index += 1
    expression = "".join(output)
    if compact_interpolations:
        expression = _compact_javascript_whitespace(expression)
    return expression, index


def _copy_javascript_template_literal(
    source,
    index,
    compact_interpolations=False,
):
    result = ["`"]
    index += 1
    while index < len(source):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""
        if char == "\\":
            result.append(char)
            index += 1
            if index < len(source):
                result.append(source[index])
                index += 1
            continue
        if char == "`":
            result.append(char)
            return "".join(result), index + 1
        if char == "$" and next_char == "{":
            result.append("${")
            expression, index = _copy_javascript_template_expression(
                source,
                index + 2,
                compact_interpolations=compact_interpolations,
            )
            result.append(expression)
            if index < len(source) and source[index] == "}":
                result.append("}")
                index += 1
            continue
        result.append(char)
        index += 1
    return "".join(result), index


def _copy_javascript_regex_literal(source, index):
    result = ["/"]
    index += 1
    escaped = False
    in_class = False
    while index < len(source):
        char = source[index]
        result.append(char)
        index += 1
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "[":
            in_class = True
            continue
        if char == "]":
            in_class = False
            continue
        if char == "/" and not in_class:
            while index < len(source) and _javascript_identifier_char(source[index]):
                result.append(source[index])
                index += 1
            break
    return "".join(result), index


def _strip_javascript_comments(source):
    source = _decode_frontend_javascript_content(source)
    output = []
    index = 0
    while index < len(source):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""
        if char == "#" and next_char == "!" and (
            index == 0 or source[index - 1] in "\r\n"
        ):
            index += 2
            while index < len(source) and source[index] not in "\r\n":
                index += 1
            output.append("\n")
            continue
        if char in ("'", '"'):
            literal, index = _copy_javascript_string_literal(source, index, char)
            output.append(literal)
            continue
        if char == "`":
            literal, index = _copy_javascript_template_literal(source, index)
            output.append(literal)
            continue
        if char == "/" and next_char == "/":
            index += 2
            while index < len(source) and source[index] not in "\r\n":
                index += 1
            output.append("\n")
            continue
        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < len(source) and not (
                source[index] == "*" and source[index + 1] == "/"
            ):
                index += 1
            index = min(index + 2, len(source))
            output.append(" ")
            continue
        if char == "/" and _javascript_previous_token_allows_regex(output):
            literal, index = _copy_javascript_regex_literal(source, index)
            output.append(literal)
            continue
        output.append(char)
        index += 1
    return "".join(output)


def _javascript_space_is_required(output_chars, current_char):
    previous, previous_identifier = _javascript_previous_nonspace_and_identifier(
        output_chars
    )
    if not previous:
        return False
    if _javascript_identifier_char(previous) and _javascript_identifier_char(current_char):
        return True
    if previous in ("+", "-") and current_char == previous:
        return True
    if previous == "/" and current_char in ("/", "*"):
        return True
    if current_char in ("'", '"', "`", "/", "[", "{", "("):
        if previous_identifier in {
            "return",
            "throw",
            "case",
            "yield",
            "await",
            "typeof",
            "void",
            "delete",
            "new",
        }:
            return True
    if previous in (")", "]") and _javascript_identifier_char(current_char):
        return True
    return False


def _compact_javascript_whitespace(source):
    source = _decode_frontend_javascript_content(source)
    output = []
    pending_space = False
    pending_newline = False
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            pending_space = True
            if char in "\r\n":
                pending_newline = True
            index += 1
            continue
        if char in ("'", '"'):
            if pending_space and _javascript_space_is_required(output, char):
                output.append("\n" if pending_newline else " ")
            literal, index = _copy_javascript_string_literal(source, index, char)
            output.append(literal)
            pending_space = False
            pending_newline = False
            continue
        if char == "`":
            if pending_space and _javascript_space_is_required(output, char):
                output.append("\n" if pending_newline else " ")
            literal, index = _copy_javascript_template_literal(
                source,
                index,
                compact_interpolations=True,
            )
            output.append(literal)
            pending_space = False
            pending_newline = False
            continue
        if char == "/" and _javascript_previous_token_allows_regex(output):
            if pending_space and _javascript_space_is_required(output, char):
                output.append("\n" if pending_newline else " ")
            literal, index = _copy_javascript_regex_literal(source, index)
            output.append(literal)
            pending_space = False
            pending_newline = False
            continue
        if pending_space and _javascript_space_is_required(output, char):
            output.append("\n" if pending_newline else " ")
        output.append(char)
        pending_space = False
        pending_newline = False
        index += 1
    return "".join(output).strip()


def _get_frontend_js_anti_debug_guard():
    return r"""
;(function(g){
  "use strict";
  if(!g||g.__FRONTEND_JS_ANTI_DEBUG__)return;
  var k="__"+"MAP_KEY_RUNTIME"+"__";
  function mark(reason){
    try{Object.defineProperty(g,"__FRONTEND_JS_HOOK_BLOCKED__",{value:reason||"debug",configurable:false,writable:false});}
    catch(_){g.__FRONTEND_JS_HOOK_BLOCKED__=reason||"debug";}
    try{
      var rt=g[k];
      if(rt&&rt.decryptMapProviderKeys){
        Object.defineProperty(rt,"decryptMapProviderKeys",{value:function(){return Promise.reject(new Error("Runtime locked"));},configurable:false});
      }
    }catch(_){}
  }
  try{Object.defineProperty(g,"__FRONTEND_JS_ANTI_DEBUG__",{value:1,configurable:false,writable:false});}
  catch(_){g.__FRONTEND_JS_ANTI_DEBUG__=1;}
  function checkSize(){
    try{
      if((g.outerWidth-g.innerWidth>160)||(g.outerHeight-g.innerHeight>160))mark("devtools");
    }catch(_){}
  }
  try{
    g.addEventListener("keydown",function(e){
      var key=String(e.key||"");
      if(key==="F12"||(e.ctrlKey&&e.shiftKey&&/[ICJ]/i.test(key))||(e.ctrlKey&&/U/i.test(key))){
        e.preventDefault();
        e.stopPropagation();
        mark("shortcut");
      }
    },true);
  }catch(_){}
  try{setInterval(checkSize,1500);checkSize();}catch(_){}
  try{
    setInterval(function(){
      var perf=g.performance;
      if(!perf||!perf.now)return;
      var started=perf.now();
      Function("debugger")();
      if(perf.now()-started>120)mark("debugger");
    },2500);
  }catch(_){}
})(typeof window!=="undefined"?window:globalThis);
"""


def _harden_frontend_javascript_for_response(source):
    source = _decode_frontend_javascript_content(source)
    if not _main()._is_frontend_js_hardening_enabled():
        return source
    guarded_source = _get_frontend_js_anti_debug_guard() + "\n" + source
    return _compact_javascript_whitespace(_strip_javascript_comments(guarded_source))
