# Changelog - Provision ONUS

## [Fase 4] Bulk TR-069 Prefetching Optimization - Feb 23, 2026

### ✅ New Feature: 10x Performance Improvement

#### **TR-069 Bulk Prefetching**
- **Problem**: Individual per-ONU validation was slow (12-15s per ONU × 171 ONUs = 34+ minutes)
- **Solution**: Single bulk query `display service-port all` to identify ALL ONUs with TR-069
- **Key Changes**:
  - New function `get_onus_with_tr069_bulk()` queries OLT once
  - Parses VLAN 150 service-ports (TR-069 indicator) to build set of already-configured ONUs
  - Filters CSV locally before processing loop
  - Eliminates ~12-15s per-ONU checks → single 2-3s query
  - **Expected performance**: 34min → 4min for typical 171 ONUs batch (10x improvement)

#### **Fall-back Strategy**
- If bulk query fails or returns unexpected format, gracefully falls back to individual checks
- Zero risk to provisioning workflow

#### **Files Modified**:
1. **omci.py** - Added `get_onus_with_tr069_bulk()` function
2. **app.py** - Integrated bulk prefetching before main processing loop
3. **TR069_BULK_OPTIMIZATION.md** - Comprehensive technical documentation

---

## [Fase 3] TR-069 Validation Implementation - Feb 19, 2026

### ✅ Completed

#### 1. **TR-069 Profile Detection (Fixed)**
- **Issue**: ONUs with TR-069 already configured were being re-provisioned, creating duplicate WANs
- **Solution**: Implemented `check_onu_tr069_profile()` function that queries OLT via `display ont info` command
- **Key Changes**:
  - Uses `send_command_timing()` instead of `send_command()` to avoid netmiko prompt detection timeout issues
  - Implements pagination handling with `write_channel()` loop to capture full output (100+ lines)
  - Supports multiple TR-069 field formats:
    - Huawei standard: `"TR069 server profile ID      : 1"`
    - Huawei variant: `"tr069-server-profile_1        : 1"`
  - Compatible with Huawei OLTs (Villa Dolores 2, OLTHUAWEI, OLT San_Jose)
  - ZTE C600 returns False (not supported yet)

#### 2. **Pagination Handling (Critical)**
- **Problem**: `display ont info` output paginated with "---- More ( Press 'Q' to break ) ----" 
- **Root Cause**: Even with `screen-length 0 temporary`, Huawei OLTs page long outputs
- **Solution**: 
  - Detect pagination indicators in output
  - Send space character via `write_channel(" ")` to advance pages
  - Concatenate all pages until complete
  - Max 20 iterations safety limit
  - Result: Captures full 8,318+ character output vs initial 972 chars

#### 3. **Logging Optimization**
- Removed debug logging clutter from execution logs
- Simplified messages to focus on provisioning status:
  - `[INFO] Chequeando TR-069 en ONU X (usuario)...`
  - `[SKIP] ONU X ya tiene TR-069 configurado (ProfileId 1)` - when skipped
  - `[INFO] ONU X sin TR-069 configurado, se procesará` - when processed

#### 4. **Integration with Provisioning Flow**
- Added `skip_tr069_configured` flag to GUI for enabling/disabling validation
- When enabled, checks TR-069 before provisioning each ONU
- Skips ONUs that already have TR-069 configured
- Updates `total_skipped` counter in real-time statistics

### 📝 Technical Details

#### Files Modified:
1. **omci.py**
   - Added `check_onu_tr069_profile()` function with full pagination handling
   - Supports regex-based profile ID detection (3 different patterns)
   - Graceful error handling (assumes no TR-069 if query fails)

2. **app.py**
   - Integrated TR-069 check in main provisioning loop
   - Simplified log messages for clarity
   - Updates skipped ONU counters

#### Code Flow:
```
Main Loop
├─ Load ONU data
├─ Check skip_tr069_configured flag
│  ├─ Call check_onu_tr069_profile()
│  │  ├─ Enter interface gpon 0/{slot}
│  │  ├─ Disable pagination: screen-length 0 temporary
│  │  ├─ Send: display ont info {port} {onu_id}
│  │  ├─ Handle pagination (loop + space character)
│  │  ├─ Parse TR069 profile ID with regex
│  │  └─ Exit interface gpon
│  │
│  ├─ If TR-069 found: Skip ONU, increment skipped counter
│  └─ If not found: Continue to provisioning
│
├─ Provision ONU (if not skipped)
└─ Update statistics
```

#### Performance Metrics:
- **Pagination time**: ~0.5s per page × 20 pages = ~10s total per ONU
- **Output capture**: 8,318 characters across 21 pages
- **Regex matching**: <10ms for profile ID extraction
- **Total check time per ONU**: ~12-15 seconds (acceptable vs re-provisioning cost)

#### Compatibility:
- ✅ OLTHUAWEI (138.59.175.17) - Working
- ✅ Villa Dolores 2 (10.11.104.5) - Working
- ✅ OLT San_Jose (138.59.175.11) - Working
- ⚠️ ZTE C600 - Not supported (returns False, ONUs processed normally)

### 🔍 Debugging Journey

#### Attempts & Resolutions:
1. ❌ `send_command()` with find_prompt() → 60s timeout on OLTHUAWEI
2. ❌ Increased read_timeout (10s → 30s → 60s) → Still failed
3. ❌ Manual write_channel/read_channel without pagination → Incomplete output
4. ✅ `send_command_timing()` + pagination loop → Works perfectly

#### Root Cause Analysis:
- After `interface gpon 0/0` command, prompt changes from `MA5608T(config)#` to `MA5608T(config-if-gpon-0/0)#`
- Netmiko's `send_command()` struggled detecting this prompt change on OLTHUAWEI
- `send_command_timing()` bypasses prompt detection, uses fixed timeout instead
- Pagination wasn't handled, requiring manual space-sending to get full output

### 📊 Impact

#### Before:
- All ONUs processed regardless of TR-069 configuration
- Risk of creating duplicate WANs on already-configured ONUs
- No visibility into skipped ONUs

#### After:
- TR-069 configured ONUs automatically skipped
- Prevents duplicate WAN provisioning
- Real-time skip counter in GUI
- Cleaner execution logs without debug clutter

### 🚀 Usage

1. **Enable TR-069 Validation**: Check "Skip TR-069 Configured" in GUI
2. **Run Provisioning**: Load CSV and start
3. **Monitor**: Watch real-time statistics:
   - Provisioned: Count of newly configured ONUs
   - Skipped: Count of ONUs with existing TR-069
4. **Review Logs**: See concise messages about each ONU's status

### 📝 Commits

- `cd6e329` - refactor: simplify TR-069 validation log messages
- `3f08914` - refactor: clean up TR-069 validation logging output
- `0ae8e26` - fix: handle pagination in TR-069 validation with write_channel loop
- `274f5af` - fix: use send_command_timing() for TR-069 validation to avoid prompt detection issues
- `47804ad` - fix: disable TR-069 validation for problematic OLTs (temporary, reverted)

