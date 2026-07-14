# Phase 05 — Frontend Split

## Context Links
- Report Python: `plans/reports/reviewer-python-260713-1257-codebase-refactor.md` (M7, M8, L2, L3, "Vai trò digest.js")
- Độc lập — có thể chạy song song bất kỳ phase nào (khác vùng file).

## Overview
- **Priority:** P3 (rủi ro thấp, không gấp)
- **Status:** completed
- **Effort:** ~3h
- Tách CSS inline khỏi index.html (345→~50 dòng); chia digest.js (363) thành nhiều file nạp tuần tự (no bundler); dọn vocabulary trùng.

## Key Insights
- `digest.js` là **client-side renderer** (browser), KHÔNG trùng logic generation Python → **GIỮ LẠI**, chỉ tách file.
- index.html ~300/345 dòng là CSS inline (M7).
- No bundler → tách bằng nhiều `<script>`/`<link>`, giữ global functions để tránh module loader (Q#8 mặc định chấp nhận).
- L3 (Python↔JS vocabulary legacy): config.json là nguồn sự thật; digest.js giữ bản fallback riêng (chấp nhận, chỉ tài liệu hoá 1 chỗ tránh drift).

## Requirements
- Functional: trang render **giống hệt** (ToC, hash router, card daily/weekly/monthly) sau tách.
- Non-functional: index.html < ~60 dòng HTML thuần; mỗi JS file < 200 LOC.

## Related Code Files
**Tạo:**
- `styles.css` — toàn bộ CSS từ index.html:13-317 (M7), link qua `<link rel="stylesheet">`.
- `date-week-utils.js` — digest.js:35-62 (M8).
- `renderers.js` — digest.js:73-172 (M8).
- `view-builder.js` — digest.js:176-231 (M8).
- `router-init.js` — phần còn lại digest.js (M8).

**Sửa:**
- `index.html` — bỏ `<style>` inline → `<link styles.css>`; thêm các `<script>` tuần tự đúng thứ tự phụ thuộc; chuyển `onclick="toggleToc"` inline → addEventListener (M7); bỏ giờ hardcode nếu chưa làm ở P1 (L2).
- `_headers` — kiểm cache/Content-Type cho .css/.js mới (nếu có rule asset).

**Xoá:** `digest.js` (thay bằng 4 file) — HOẶC giữ tên và chỉ tách phần, tuỳ Q#8.

## Implementation Steps
1. Cắt CSS block → `styles.css`; index.html thêm `<link>`; xác nhận render pixel giống.
2. Chia digest.js theo ranh dòng (M8); giữ tên global function không đổi (renderCard, initRouter…).
3. Thêm `<script src>` tuần tự: date-week-utils → renderers → view-builder → router-init.
4. Chuyển `toggleToc` inline onclick → addEventListener trong router-init.js.
5. Kiểm `_headers` phục vụ .css/.js đúng MIME + cache.
6. Đảm bảo `deploy-cloudflare-pages.yml` deploy các asset mới (static → tự động; xác nhận không allowlist file cụ thể).

## Todo
- [x] styles.css tách khỏi index.html (303 dòng, `<link rel="stylesheet">`)
- [x] Chia digest.js → 4 file (date-week-utils.js, renderers.js, view-builder.js, router-init.js); digest.js đã xoá
- [x] `<script>` tuần tự đúng thứ tự (date-week-utils → renderers → view-builder → router-init)
- [x] toggleToc → addEventListener (`data-toggle-toc` attr + `querySelectorAll` bind trong `init()`)
- [x] _headers phục vụ asset mới (thêm rule `/*.css`; sửa comment "5AM"→"9AM")
- [x] index.html < 60 dòng (43); mỗi JS < 200 LOC (32/134/136/67)
- [x] Fix giờ hardcode "5h/5AM" → "9h/9AM" khớp config.json (L2)

## Success Criteria
- Mở trang local (hoặc Pages preview): ToC + router + render 3 loại card **giống hệt** trước.
- Không lỗi console (thiếu function/undefined do sai thứ tự script).
- `wc -l index.html` < 60; mỗi `.js` mới < 200.

## Risk
- Thấp. Rủi ro chính: sai thứ tự `<script>` → global chưa định nghĩa. Verify thứ tự phụ thuộc trước.
- CSS tách thiếu selector → lệch layout. Diff visual trước/sau.

## Security Considerations
- Không có secret ở frontend. `_headers` giữ CSP/cache hiện có, không nới.

## Next Steps
- Không mở khoá phase khác. Có thể làm bất kỳ lúc nào.
- L3 vocabulary drift: ghi chú field legacy (news/repos/gamingNews) ở 1 nơi (README hoặc comment config) — task doc nhỏ, tuỳ chọn.
