const UUID_PATTERN = /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i

export function isValidUUID(val) {
  return typeof val === 'string' && UUID_PATTERN.test(val)
}

export function isUsableSessionUUID(val) {
  if (!val || typeof val !== 'string') return false
  if (val === 'None' || val === 'null' || val === 'undefined' || val.trim() === '') return false
  return isValidUUID(val)
}

export function isValidUsername(username) {
  if (!username || typeof username !== 'string') return false
  return username.length >= 3 && username.length <= 32 && /^[a-zA-Z0-9_一-鿿]+$/.test(username)
}

export function isValidPassword(password) {
  return typeof password === 'string' && password.length >= 6 && password.length <= 64
}

export function isValidPhone(phone) {
  return typeof phone === 'string' && /^1[3-9]\d{9}$/.test(phone)
}
