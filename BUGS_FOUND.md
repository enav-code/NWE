# Bugs and Issues Found

## Critical Issues

### 1. **Case Sensitivity Bug - File Not Found** (App.py, Lines 112 & 128)
- **Severity**: HIGH
- **Issue**: Routes request "index.html" but the actual file is "Index.html" (capital I)
- **Lines**: 
  - Line 112: `return send_from_directory(app.static_folder, "index.html")`
  - Line 128: `return send_from_directory(app.static_folder, "index.html")`
- **Impact**: Users will get 404 errors when trying to access `/` or `/dashboard`
- **Fix**: Change to `"Index.html"` to match the actual filename

### 2. **Missing DOM Element Reference** (app.js, Line 86)
- **Severity**: MEDIUM
- **Issue**: Code references `$('#reminder-button')` but this element doesn't exist in Index.html
- **Line**: `$('#reminder-button').addEventListener('click', () => alert('Reminder creation is next in the MVP roadmap.'));`
- **Impact**: JavaScript console error, breaks event listener setup
- **Fix**: Either add the element to HTML or remove this line

### 3. **Database Insert Field Order Mismatch** (App.py, Lines 166-167)
- **Severity**: HIGH
- **Issue**: The INSERT statement field order doesn't match the dictionary value order
```python
extracted = {"name": name, "category": category, "vendor": vendor, "price": price, "purchased_on": purchased, "warranty_until": warranty, "return_until": return_until}
# Later inserted as:
cursor.execute("INSERT INTO assets (name, category, vendor, price, purchased_on, warranty_until, return_until, location, document_name, created_at) VALUES (...)", (*extracted.values(), datetime.utcnow().isoformat()))
```
- **Problem**: `extracted` dict doesn't have "location" key, so the insert will fail or insert wrong data
- **Impact**: Document imports will fail
- **Fix**: Add "location" to extracted dict before inserting

### 4. **DOM Structure Assumptions** (app.js, Lines 21-25)
- **Severity**: MEDIUM
- **Issue**: Code assumes specific DOM elements exist without checking:
```javascript
document.querySelector('.warning-card > strong').textContent = '0';
document.querySelector('.warning-card .warning').textContent = '● No deadlines yet';
document.querySelector('.reminder-list').innerHTML = '...';
document.querySelector('.insight-banner h3').textContent = '...';
```
- **Impact**: Will throw errors if DOM structure changes
- **Fix**: Add null checks or verify elements exist before manipulating

### 5. **Potential Session Security Issue** (App.py, Line 157)
- **Severity**: MEDIUM
- **Issue**: Google profile data is stored directly in session without sanitization
```python
session["user"] = {key: profile.get(key, "") for key in ("sub", "name", "email", "picture")}
```
- **Problem**: Should validate that required fields exist (at minimum "sub" and "email")
- **Impact**: Could create invalid sessions
- **Fix**: Add validation for required fields

### 6. **No Error Handling for Missing .env** (App.py, Line 12)
- **Severity**: MEDIUM
- **Issue**: `load_dotenv()` silently fails if `.env` doesn't exist
- **Problem**: `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` will be empty strings, allowing the app to start but OAuth will fail silently
- **Impact**: Users get confusing errors instead of clear configuration instructions
- **Fix**: Add validation that required env vars exist

## Minor Issues

### 7. **Database Connection Not Closed** (App.py)
- **Severity**: LOW
- **Issue**: Using `with db() as connection` is good, but SQLite connections should have `check_same_thread=False` for Flask
- **Impact**: May cause threading issues in production
- **Fix**: Add `check_same_thread=False` to sqlite3.connect()

### 8. **No Input Validation for Asset Creation** (App.py, Line 149)
- **Severity**: LOW
- **Issue**: Only validates name, doesn't validate other fields like price (should be numeric)
- **Impact**: Could insert invalid data
- **Fix**: Validate price is float, dates are valid ISO format

### 9. **Case Sensitive File References** (Multiple)
- **Severity**: LOW
- **Issue**: "Index.html" vs "index.html" will fail on Linux/production servers
- **Impact**: App works on Windows (case-insensitive) but fails on Linux
- **Fix**: Rename file to lowercase "index.html" and update all references

### 10. **Missing Reminders Endpoints** (App.py)
- **Severity**: MEDIUM
- **Issue**: `/api/reminders` endpoint exists (line 179) but there's no POST endpoint to create reminders
- **Problem**: The UI says "Reminder creation is next in the MVP roadmap" (line 86 of app.js)
- **Impact**: Feature is incomplete

## Summary

**Total Issues Found**: 10
- **Critical/High**: 3 (will cause runtime failures)
- **Medium**: 4 (will cause issues in production or edge cases)
- **Low**: 3 (quality improvements)

**Priority Fixes**:
1. Fix "index.html" → "Index.html" case sensitivity (or rename file)
2. Fix import field order mismatch
3. Add missing DOM element or remove reference
