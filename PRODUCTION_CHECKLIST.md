# Production Readiness Checklist

Pre-production audit checklist for the DFTL Ranking Dashboard.

---

## 1. Functional Testing

### Tab 1: Rankings
- [x] Rankings load and display correctly for both datasets
- [x] Sort controls work (Rating, Games, Win Rate, etc.)
- [x] Ranked vs Unranked players display differently (coral vs blue)
- [x] Podium icons display for ranks 1-3
- [x] Player links navigate to Tracker tab with correct player
- [x] Card stats grid shows all 8 metrics correctly

### Tab 2: Hall of Fame
- [x] All 5 leaderboard cards populate with data
- [x] Ties are handled correctly (all tied players shown)
- [x] Elo #1 Timeline chart renders
- [x] Chart is theme-adaptive (transparent backgrounds)

### Tab 3: Player Tracker
- [x] Player selector populates with all players
- [x] URL param `?player=Name` pre-selects player
- [x] Rating History chart renders correctly
- [x] Game History cards display with correct data
- [x] Date links navigate to Dailies tab

### Tab 4: Dailies
- [x] Date picker works and constrains to valid range
- [x] Cards display for selected date
- [x] Sort by Rank/Score works
- [x] Player links work
- [x] Cards constrained to 600px width

### Cross-Tab Features
- [x] Dataset toggle badge updates immediately
- [x] Consecutive dataset switches work correctly
- [x] Share button copies correct URL
- [x] Internal navigation preserves dataset selection
- [x] URL params persist on refresh

---

## 2. Responsive Design

### Breakpoints to Test
- [x] 400px (mobile portrait)
- [x] 600px (mobile landscape / small tablet)
- [x] 816px (container query breakpoint)
- [x] 900px (tablet)
- [x] 1200px+ (desktop)

### Components to Verify
- [x] Header banner scales (logo, title, badge)
- [x] Card grids collapse from 8-col to 4-col at 816px
- [x] Sidebar collapses on mobile
- [x] Date pickers remain side-by-side (not stacked)
- [x] Labels don't wrap (DAILY TOP10 (%) especially)
- [x] Charts are readable at all sizes

---

## 3. Theme Compatibility

### Dark Mode
- [x] All text readable on dark background
- [x] Card backgrounds have correct gradients
- [x] Charts have transparent backgrounds
- [x] Accent colors (coral, blue, green) visible

### Light Mode
- [x] All text readable on light background
- [x] Card backgrounds adapt
- [x] No hardcoded dark-mode colors showing
- [x] Dataset badge colors work (green/blue)

### Mid-Session Switch
- [x] Switching themes in Streamlit settings updates UI
- [x] CSS variables resolve correctly
- [x] No stale Python-generated colors

---

## 4. Accessibility (WCAG)

### Contrast Ratios
- [x] Body text: 4.5:1 minimum
- [x] Large text (labels): 3:1 minimum
- [x] Coral accent on dark bg: passes
- [x] Coral accent on light bg: uses darker variant
- [x] Blue accent (unranked): passes in both themes

### Keyboard Navigation
- [x] Tab order is logical
- [x] All interactive elements focusable (tabs, share button, links, back-to-top)
- [x] No keyboard traps
- [x] Focus indicators visible (coral outline, 2px solid)

### Screen Readers
- [x] Meaningful alt text where applicable
- [x] ARIA labels on interactive elements
- [x] Logical heading hierarchy

---

## 5. Data Integrity

### Elo Calculations
- [x] Ratings match expected values for known players
- [x] Rating changes sum correctly over history
- [x] Compression function produces expected outputs
- [x] Floor (1000) and ceiling (3000) enforced

### Statistics
- [x] Games played counts match actual appearances
- [x] Win counts match rank #1 occurrences
- [x] Win rate = wins / games × 100
- [x] Top 10 rate calculated correctly
- [x] 7-game average uses last 7 games only
- [x] Daily variance calculated correctly

### Edge Cases
- [x] Player with 0 games handled
- [x] Player with exactly 7 games (threshold)
- [x] Player inactive for exactly 7 days
- [x] Dates with missing data
- [x] Empty dataset scenario

---

## 6. Performance

### Load Times
- [x] Initial page load < 3 seconds
- [x] Tab switching feels instant
- [x] Large player lists don't lag
- [x] Charts render without delay

### Caching
- [x] `@st.cache_data` used for data loading
- [x] Cache invalidation works when data updates
- [x] No stale data after refresh

### Resource Usage
- [x] No memory leaks on extended use
- [x] Reasonable memory footprint
- [x] No excessive re-renders

---

## 7. Security

### XSS Prevention
- [x] Player names escaped in HTML output
- [x] URL params sanitized before use
- [x] No `eval()` or `exec()` on user input

### Data Exposure
- [x] No Discord IDs in published data
- [x] No sensitive paths exposed
- [x] No API keys in client-side code
- [x] `.env` files gitignored

### URL Params
- [x] Invalid tab names handled gracefully
- [x] Invalid player names don't crash
- [x] Invalid dates handled
- [x] Malformed params don't cause errors

---

## 8. Error Handling

### Missing Data
- [x] Missing CSV files show user-friendly message
- [x] Partial data loads gracefully
- [x] NaN/null values display as "—"

### Invalid States
- [x] Empty search results show message
- [x] No players in dataset handled
- [x] Date outside range handled

### Network Issues
- [x] App works offline after initial load
- [x] Font loading failure doesn't break layout

---

## 9. Cross-Browser Testing

### Desktop Browsers
- [x] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)

### Mobile Browsers
- [x] Chrome Mobile (Android)
- [ ] Safari Mobile (iOS)

### Feature Support
- [x] CSS container queries (`@container`)
- [x] CSS `:has()` selector
- [x] Dark mode only (no `light-dark()` - supports Chrome 105+)

---

## 10. Code Quality

### Dead Code
- [x] No unused imports
- [x] No commented-out code blocks
- [x] No unused functions
- [x] No orphaned CSS rules

### Consistency
- [x] Consistent naming conventions
- [x] Consistent spacing/indentation
- [x] Consistent use of CSS variables vs hardcoded values

### Documentation
- [x] Functions have docstrings
- [x] Complex logic has comments
- [x] CLAUDE.md is up-to-date
- [x] README reflects current features

---

## 11. Deployment Configuration

### Dependencies
- [x] `requirements.txt` complete and pinned
- [x] No unnecessary dependencies
- [x] Python version specified

### Streamlit Config
- [x] `.streamlit/config.toml` has correct settings
- [x] Theme colors defined
- [x] Server settings appropriate for production

### Environment
- [x] No hardcoded localhost URLs
- [x] Domain detection works (`st.context.headers`)
- [x] HTTPS URLs generated (not HTTP)

### Hosting (Render/HF Spaces)
- [x] Start command correct
- [x] Port configuration correct
- [x] Build settings correct

---

## 12. Data Files

### CSV Files
- [x] All required CSVs present in `data/processed/`
- [x] File encoding is UTF-8
- [x] No BOM issues
- [x] Column names match code expectations

### Both Datasets
- [x] `full_*.csv` files present
- [x] `early_access_*.csv` files present
- [x] Both datasets load without errors

---

## 13. Git/Version Control

### Repository State
- [x] No sensitive files committed
- [x] `.gitignore` covers all necessary files
- [x] No large binary files (or using Git LFS)
- [x] Clean commit history

### Release
- [x] Version tag created
- [x] Release notes written
- [x] Changelog updated (if applicable)

---

## 14. Final Smoke Test

- [ ] Fresh browser (incognito) loads correctly
- [ ] Direct URL to each tab works
- [ ] Share URL works when sent to another device
- [ ] All features work on mobile device
- [ ] No console errors in browser DevTools
- [ ] No Python errors in Streamlit logs

---

## Sign-Off

| Area | Reviewer | Date | Status |
|------|----------|------|--------|
| Functional | | | |
| Responsive | | | |
| Accessibility | | | |
| Performance | | | |
| Security | | | |
| Code Quality | | | |

---

*Last updated: 2026-02-07*
