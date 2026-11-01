# Samsung classroom dashboard

Independent design for the attendance application. Public inspiration: https://getdesign.md/ describes documenting colors, typography, spacing and components in DESIGN.md. No paid starter-kit source or private specification is used.

- Navy gradient sidebar (#183a67 to #102747) with light text and blue active navigation; white panels on a pale blue-gray canvas. Primary action blue #245cce, body text #18243a, secondary text #637086, borders #e0e6ef.
- Segoe UI with Arial fallback; body 15px, page titles 30px, section titles 17px, controls 13–14px. No downloaded font dependency added.
- Spacing uses 4/8/12/16/20/24/32px steps; panel corners 10–11px, controls 7px. Keep shadows subtle.
- Preserve Samsung logo and Lớp học Samsung identity. Titles name the task: Tổng quan, Điểm danh, Học sinh, Lớp học, Lịch sử điểm danh. Descriptions should be one short useful sentence. No motivational slogans.
- Success stays green, attention amber, errors distinct. Show labels in addition to color. Visible keyboard focus, responsive layout and reduced-motion support are required.
- Desktop uses a left sidebar; small screens use labeled navigation above content. Tables may scroll horizontally. Do not shrink text to fit desktop tables onto phones.
- Camera overlays and captured viewport must remain mathematically aligned with face_inside_guide. Cosmetic work must not change recognition, enrollment, sessions, or database behavior.
- dashboard.css owns the refreshed visual styling; styles.css retains base structure and camera geometry.


Workspace color accents: pale blue heading and section headers; blue for totals, green for attendance, amber for pending, lavender for attendance rate. Keep dark readable text and white table bodies. Colors supplement labels; do not change camera crop or oval geometry.
