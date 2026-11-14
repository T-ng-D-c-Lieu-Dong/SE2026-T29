from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from xml.sax.saxutils import escape
import os
pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('ArialBold', 'C:/Windows/Fonts/arialbd.ttf'))
os.makedirs('output/pdf',exist_ok=True)
path='output/pdf/BT3_23001839_VT-117.pdf'
body=ParagraphStyle('body',fontName='Arial',fontSize=9.1,leading=13,spaceAfter=6)
head=ParagraphStyle('head',fontName='ArialBold',fontSize=13,leading=17,spaceBefore=7,spaceAfter=7,textColor=colors.HexColor('#16345a'))
title=ParagraphStyle('title',fontName='ArialBold',fontSize=17,leading=21,spaceAfter=12,textColor=colors.HexColor('#16345a'))
small=ParagraphStyle('small',fontName='Arial',fontSize=7.5,leading=10)
story=[]
def p(s): story.append(Paragraph(escape(s),body))
def h(s): story.append(Paragraph(escape(s),head))
def page(): story.append(PageBreak())
def table(rows, widths):
 t=Table([[Paragraph(escape(str(c)),small) for c in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dce8f4')),('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#abb9c9')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),4)]));story.append(t);story.append(Spacer(1,8))
story.append(Paragraph('BT CÁ NHÂN 3 • VT-117',title))
p('Vũ Thành Công • 23001839 • Thành viên • SE2026-T29 • APP-03 Production Readiness Lab')
p('Repository: https://github.com/CuongMotNang/SE2026-T29 (GitHub chuyển tới T-ng-D-c-Lieu-Dong/SE2026-T29). Baseline: 2a4bbc3b246e1f2c9b947a4d8de56489a4b37fc9. Nhánh: https://github.com/T-ng-D-c-Lieu-Dong/SE2026-T29/tree/bt3-23001839-vt117')
p('Cam kết để sinh viên tự xác nhận trước khi nộp: “Tôi chịu trách nhiệm về toàn bộ code, test và nội dung bài làm; tôi đã khai báo việc sử dụng AI.”')
h('1. Specification và contract')
p('Vấn đề: giá trị mặc định số appointment trên một trang được cố định trong API; người vận hành cần thay đổi giá trị nghiệp vụ này qua cấu hình tập trung mà không sửa mã ở nhiều nơi.')
p('AC1: Không cấu hình thì mặc định 20. AC2: BOOKING_DEFAULT_PAGE_SIZE nhận số nguyên từ 1 đến 100; giá trị khác bị từ chối khi nạp settings. AC3: Khi không gửi limit, API dùng cấu hình và trả đúng limit, offset, total và items. AC4: limit hợp lệ do client gửi được ưu tiên; limit ngoài 1–100 trả 422. AC5: lỗi repository không được chuyển thành kết quả rỗng thành công.')
p('Invariant: phản hồi thành công phải phản ánh kết quả repository và phân trang thực; lỗi truy xuất không được che giấu bằng total=0. Ràng buộc: giữ contract query 1–100 và mặc định 20; cấu hình được cache trong process và yêu cầu khởi động lại; mục tiêu tải 120 tác vụ, p95 không quá 3,5 giây.')
h('2. Plan và review trước patch')
p('Prompt tóm tắt: giải thích contract và invariant trước, đối chiếu requirements repository, lập plan và danh sách file; viết test fail trước, sửa nhỏ, kiểm tra mutation nuốt exception và tải 120 tác vụ. Giả định: cấu hình trang mặc định là một cấu hình nghiệp vụ phù hợp; không thay endpoint hay cấu trúc dữ liệu.')
p('Hai điều chỉnh dựa trên repository: (1) không chọn SLOT_MINUTES: booking.py dùng nó để liệt kê slot và kiểm tra mốc 30 phút, thay riêng sẽ phá nhất quán; (2) không cấu hình mức trần 100: appointments.py và test_appointments_api.py đã công bố và kiểm thử cận này. Plan cuối sửa config.py, api/appointments.py, test contract và README; thêm harness và evidence.')
page();h('3. Chiến lược và test cases')
p('Contract testing ở đây kiểm tra provider qua HTTP ASGI, gồm metadata và nội dung, cùng kiểm tra boundary settings; đây không phải consumer-driven contract có broker. Unit bao phủ validation và failure path; integration cần PostgreSQL thật; E2E qua UI để xác nhận luồng người dùng là bước tiếp theo. Không cần E2E cho từng giá trị biên vì lặp lại logic API và tăng chi phí.')
rows=[['ID / ưu tiên','Risk / đầu vào','Kết quả / mức / trạng thái'],['T01 P1','Không có biến môi trường','20 / unit / pass'],['T02 P1','Cấu hình 7','Settings = 7 / unit / pass'],['T03 P1','Biên 1','Chấp nhận / unit / pass'],['T04 P1','Biên 100','Chấp nhận / unit / pass'],['T05 P1','Cấu hình 0','ValidationError / unit / pass'],['T06 P1','Cấu hình 101','ValidationError / unit / pass'],['T07 P1','Cấu hình chữ invalid','ValidationError / unit / pass'],['T08 P1','Không gửi limit, config 7, offset 1','200, limit 7, total 12, tên Lan / API giả / pass'],['T09 P1','Gửi limit 3, config 7','limit 3 và dữ liệu phân trang / API giả / pass'],['T10 P1','limit 0 hoặc 101','422 / API giả / pass'],['T11 P1','Repository raise RuntimeError','Exception lan truyền / unit / pass'],['T12 P1','Hai booking, config 1','Một mục, total 2 / PostgreSQL integration / pass']]
table(rows,[85,175,235])
p('Dữ liệu chọn theo lớp tương đương và biên: 0/1/100/101, chuỗi sai kiểu, giá trị khác mặc định 7 và limit tường minh 3. Fake trả total 12 và tên Lan để phát hiện test chỉ nhìn HTTP 200. T11 là failure path; T05–T07 và T10 là negative tests.')
h('4. Test-first và review patch')
p('Baseline: 2a4bbc3. bt3_fail.log ghi 4 lỗi vì Settings chưa có default_page_size và không từ chối cấu hình sai, trước patch. Patch 6d9bf5f thêm Field(default=20, ge=1, le=100), chọn effective_limit khi query vắng, cập nhật README. Test xác nhận response thực tế; bộ unit sau mở rộng: 135 pass (bt3/unit_final.txt). PostgreSQL integration: 12 pass, bao gồm T12 (bt3/integration.txt).')
p('Review: query tường minh không bị thay thế; giá trị 0 bị FastAPI từ chối, không dùng phép “or” gây che lỗi; cấu hình cache nghĩa là đổi biến cần restart. OpenAPI không còn công bố default 20, một thay đổi mô tả contract cần nhóm review.')
page();h('5. Mutation, coverage và flaky')
p('Mutation tạm thời trong BookingService.list: bắt Exception rồi return [], 0. Chạy T11 cho kết quả DID NOT RAISE RuntimeError (bt3_mutation.log); đã khôi phục và không commit mutation. Test này chứng minh phát hiện một mutation cụ thể, không chứng minh mọi lỗi đều bị phát hiện.')
p('Coverage chạy riêng 10 test contract với coverage.py --branch: config 90%, appointments 60%, booking service 33%, tổng 53% (bao gồm nhiều nhánh không thuộc lát cắt). Không coi tỷ lệ tổng là chất lượng: thiếu đường E2E và phụ thuộc DB thật mới là rủi ro quan trọng. Xem bt3/coverage.txt để biết dòng chưa chạy.')
p('Flaky: (1) Thời gian: unit dùng ngày cố định 2030 và không phụ thuộc đồng hồ; test tích hợp dùng ngày tương lai động, còn rủi ro đổi ngày/múi giờ. (2) Shared state/thứ tự: get_settings dùng cache; test xóa cache trong finally và monkeypatch tự hoàn tác. Integration TRUNCATE dùng DB chuyên biệt; không chạy song song các test cùng DB. (3) Network và concurrency: ASGI in-process tránh mạng; benchmark vẫn chịu scheduler và không phản ánh contention DB.')
h('6. Thử tải và giới hạn')
p('bt3/load_harness.py chạy 120 coroutine đồng thời, mỗi request kiểm tra status và toàn bộ payload; fake repository ngủ 10ms. Kết quả một lượt: 120/120 outcome hợp lệ, p95 nearest-rank = 0,097715s, nhỏ hơn 3,5s trong harness này. Không có network, PostgreSQL, server worker hay dữ liệu thật; không thể kết luận hệ thống đạt SLO. Cần chạy lại nhiều lần trên môi trường đại diện, ghi lỗi, throughput, p95 và tài nguyên.')
h('7. Traceability')
table([['AC / risk','Test → file','Commit / kết quả'],['AC1–2','T01–T07 → test_page_size_contract.py','6d9bf5f, 29233a5 / pass'],['AC3','T08; T12 → unit; integration/test_appointments_api.py','6d9bf5f; 1e562d8 / pass'],['AC4','T09–T10 → test_page_size_contract.py','29233a5 / pass'],['AC5 / nuốt lỗi','T11 → test_page_size_contract.py','6d9bf5f / pass, mutation bị bắt'],['120, p95','bt3/load_harness.py','29233a5, 586b7a7 / giả lập']],[85,240,170])
p('Đường dẫn test contract đầy đủ: backend/tests/unit/test_page_size_contract.py. Bằng chứng và lệnh: bt3/README.md, bt3_fail.log, bt3_mutation.log, bt3/unit_final.txt, bt3/load_result.txt.')
page();h('8. Reflection - bản nháp để sinh viên tự đối chiếu')
p('Confidence tăng trước hết vì tôi có thể nối từng yêu cầu với một phép kiểm chứng cụ thể. Lần chạy đầu cho thấy settings chưa có trường cấu hình và không từ chối giá trị sai; sau patch, test tương ứng chuyển sang pass. Việc kiểm tra cả total, limit và tên khách hàng giúp phát hiện phản hồi có HTTP 200 nhưng sai nghiệp vụ. Mutation bắt mọi exception rồi trả danh sách rỗng cũng khiến test failure-path thất bại. Bằng chứng đó mạnh hơn việc chỉ đọc code hoặc nhìn tỷ lệ coverage, vì nó cho thấy một lỗi có chủ đích thực sự bị phát hiện. Tuy nhiên, một mutation bị bắt không có nghĩa suite phát hiện được mọi lỗi.')
p('Tôi vẫn chưa thể khẳng định hệ thống production đạt mục tiêu hiệu năng. Con số p95 được đo qua ASGI cùng tiến trình với repository giả, không có mạng, pool kết nối hoặc PostgreSQL. Test PostgreSQL đã pass nhưng bộ test contract chưa bao phủ toàn bộ luồng UI; coverage tổng thấp phần nào vì các thao tác tạo và hủy không thuộc lát cắt đang đo. Ngoài ra cấu hình được cache, nên vận hành phải khởi động lại để thay đổi có hiệu lực; mô tả OpenAPI mặc định cũng thay đổi và cần review tương thích.')
p('Test tiếp theo có giá trị cao nhất là chạy 120 request qua deployment đại diện, với PostgreSQL và dữ liệu đủ lớn, lặp lại nhiều lượt và kiểm tra cả nội dung lẫn lỗi, đồng thời đo p95 và tài nguyên. Trước khi nộp tôi cần tự đọc diff, chạy lại các lệnh, đối chiếu kết quả tích hợp thực tế và diễn đạt reflection theo hiểu biết của mình. Tôi không nên dùng kết quả giả lập như bằng chứng SLO production.')
h('Phụ lục: AI Usage Log')
p('Công cụ: Codex. Prompt chính là đề VT-117 và yêu cầu triển khai tiếp; output dùng gồm plan, test, patch, harness và bản nháp báo cáo. Đối chiếu bằng code và lệnh pytest, không dùng lời AI làm bằng chứng. Hai điểm cần nghi ngờ: test chỉ assert status 200 có thể bỏ lọt sai dữ liệu; giá trị default động làm thay đổi mô tả OpenAPI dù runtime giữ 20. Đã bổ sung assertions payload và ghi nhận rủi ro contract. Các giả định về lựa chọn cấu hình phải được nhóm/sinh viên xác nhận.')
p('Lưu ý: bản reflection và cam kết là bản nháp; sinh viên cần tự xác minh và chịu trách nhiệm trước khi nộp.')
def footer(c,doc):
 c.setFont('Arial',8);c.setFillColor(colors.grey);c.drawString(45,28,'VT-117 • 23001839');c.drawRightString(A4[0]-45,28,str(doc.page))
SimpleDocTemplate(path,pagesize=A4,rightMargin=45,leftMargin=45,topMargin=40,bottomMargin=43).build(story,onFirstPage=footer,onLaterPages=footer)
print(path)
