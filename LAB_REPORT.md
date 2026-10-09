# Hệ thống Deep Research đa tác tử với Deep Agents và Sandbox: Thiết kế, triển khai và phân tích năm báo cáo khảo sát

## Tóm tắt

Báo cáo này trình bày việc xây dựng một hệ thống nghiên cứu tự động đa tác tử: từ một chủ đề do người dùng nhập, hệ thống tự lập kế hoạch, phân rã thành các câu hỏi con, giao cho nhiều tác tử nghiên cứu chạy song song trên arXiv, Hugging Face và web, rồi tổng hợp một bản khảo sát có trích dẫn. Hệ thống được xây dựng bằng thư viện Deep Agents, dùng sandbox Daytona làm không gian làm việc và nơi chạy mã kiểm tra, trong khi các công cụ truy cập mạng và khóa API được giữ ở phía máy chủ.

Hệ thống được vận hành trên năm chủ đề: mô hình thế giới, học tăng cường cho suy luận của mô hình ngôn ngữ lớn, tác tử LLM và sử dụng công cụ, sinh video và đa phương thức, suy luận hiệu quả và mô hình ngôn ngữ nhỏ. Mỗi lần chạy tạo ra một báo cáo Markdown, một tệp nguồn có cấu trúc và một tệp siêu dữ liệu. Tổng cộng 83 nguồn và 9.747 từ được sinh ra trong 25,4 phút. Cả năm báo cáo đều có ít nhất 5 lần ủy quyền cho tác tử con, sử dụng ba họ nguồn, và vượt qua bộ kiểm tra trích dẫn tự động. Việc đối chiếu thủ công trên một mẫu nhỏ gồm khoảng 16 mệnh đề có số liệu cho thấy phần lớn khớp với nguồn, đồng thời lộ ra các dạng lỗi mà kiểm tra tự động không phát hiện được. Báo cáo phân tích các dạng lỗi đó, trình bày nội dung khoa học của từng bản khảo sát và nêu rõ phạm vi những gì đã và chưa được kiểm chứng.

**Từ khóa:** tác tử đa nhiệm, Deep Agents, nghiên cứu tự động, trích dẫn có thể kiểm chứng, sandbox, mô hình ngôn ngữ lớn.

---

## 1. Giới thiệu

Khảo sát tài liệu là công việc tốn thời gian và dễ sai sót: người viết phải tìm nguồn, đọc, đối chiếu và gán từng khẳng định cho đúng bài báo. Các mô hình ngôn ngữ lớn có thể tự động hóa phần lớn quy trình này, nhưng đồng thời tạo ra hai rủi ro đặc thù. Thứ nhất là khẳng định hoặc nguồn bịa đặt. Thứ hai, tinh vi hơn, là khẳng định đúng về nội dung nhưng gán nhầm cho một nguồn khác. Một hệ thống nghiên cứu tự động chỉ có giá trị khi người đọc kiểm tra lại được từng trích dẫn.

Bài thực hành đặt ra năm mục tiêu: (1) dựng tác tử bằng Deep Agents với công cụ, lời nhắc hệ thống, tác tử con và backend; (2) dùng sandbox làm nơi lưu tệp và chạy mã, đồng thời giữ khóa API cùng công cụ mạng ở phía máy chủ; (3) viết công cụ gọi API ngoài chịu được giới hạn tốc độ; (4) thiết kế quy trình đa tác tử gồm phân rã, song song hóa, tổng hợp và kiểm tra trích dẫn; (5) tạo báo cáo mà mọi khẳng định có số `[n]` trỏ tới một nguồn có thật.

## 2. Thiết kế hệ thống

### 2.1 Luồng xử lý

Tập lệnh chính mở một sandbox Daytona và đảm bảo sandbox luôn được dừng và xóa khi kết thúc, kể cả khi có lỗi. Hai tập lệnh kiểm tra được tải lên sandbox: bộ kiểm tra trích dẫn (viết cho bài này) và bộ hoàn thiện trích dẫn (cho sẵn). Tác tử trưởng (lead) thực hiện các bước sau.

1. Lập kế hoạch bằng công cụ `write_todos` và chia chủ đề thành ít nhất ba câu hỏi con độc lập.
2. Giao từng câu hỏi cho tác tử `researcher` qua công cụ `task`, chạy song song, kèm đủ ngữ cảnh vì tác tử con chỉ thấy tin nhắn ủy quyền.
3. Đọc các tệp ghi chú do researcher viết trong sandbox để kiểm tra kết quả trước khi dùng.
4. Gộp ghi chú thành `sources.json` (mỗi nguồn có `n`, `id`, `url`, `title`, `date`, `source`), bảo đảm có ít nhất ba họ nguồn.
5. Viết thân báo cáo theo cấu trúc quy định, không tự viết danh mục tham khảo.
6. Chạy bộ hoàn thiện trích dẫn trong sandbox: loại nguồn không được trích, gộp URL trùng, đánh số lại, chuẩn hóa dạng `[1][2]`, sinh danh mục tham khảo.
7. Chạy bộ kiểm tra trích dẫn cho đến khi in `OK`.
8. Giao tác tử `citation-checker` kiểm tra mẫu các cặp khẳng định/URL.

### 2.2 Mô hình an toàn

Nội dung lấy từ web được coi là dữ liệu không đáng tin: lời nhắc của researcher cấm làm theo chỉ dẫn nằm trong nội dung công cụ trả về và cấm bổ sung số liệu từ trí nhớ. Sandbox không ngăn được tấn công chèn lệnh hay việc đẩy dữ liệu ra mạng, vì vậy mọi công cụ truy cập mạng (arXiv, Hugging Face, Exa) chạy ở phía máy chủ, khóa API không bao giờ được tải lên sandbox, và các thông báo lỗi trả về cho tác tử đều được che khóa.

### 2.3 Các công cụ nguồn dữ liệu

| Công cụ | Nguồn | Điểm thiết kế chính |
|---|---|---|
| `arxiv_search` | API arXiv (HTTPS, Atom XML) | Khoảng cách tối thiểu 3 giây giữa hai lần gọi; làm sạch truy vấn; chuẩn hóa mã bài báo và bỏ hậu tố phiên bản; thời gian chờ tối đa dài hơn khi gặp HTTP 429 |
| `hf_daily_papers` | Hugging Face Daily Papers | Lọc từ khóa phía máy khách, sắp theo lượt bình chọn |
| `hf_search_papers` | Hugging Face papers search | Ưu tiên `ai_summary` khi có |
| `web_search`, `web_fetch` | Exa MCP qua JSON-RPC/SSE | Phát hiện giới hạn tốc độ trả về HTTP 200 qua cờ trong `result._meta` và thử lại; che khóa API; cắt nội dung trang còn khoảng 12.000 ký tự |

Tất cả công cụ trả về chuỗi, không ném ngoại lệ, trả `NO RESULTS` khi rỗng và `ERROR: ...` khi nguồn hỏng sau khi đã thử lại. Hàm `with_retry` dùng lùi lũy thừa có nhiễu ngẫu nhiên, tôn trọng tiêu đề `Retry-After`, chặn trên bằng một ngưỡng, và không chờ thêm sau lần thử cuối.

### 2.4 Kiểm soát chi phí và độ lặp

Hệ thống đặt giới hạn số lần gọi mô hình và công cụ cho cả tác tử trưởng lẫn từng tác tử con (`ModelCallLimitMiddleware`, `ToolCallLimitMiddleware`) cùng giới hạn đệ quy của đồ thị. Do giới hạn đệ quy chỉ áp cho tác tử trưởng, tác tử con được giới hạn riêng bằng middleware.

### 2.5 Bộ kiểm tra trích dẫn

Bộ kiểm tra chỉ dùng thư viện chuẩn vì chạy trong sandbox. Nó yêu cầu: danh sách nguồn không rỗng; mỗi nguồn có số nguyên `n`, URL bắt đầu bằng `http://` hoặc `https://` và không trùng URL; báo cáo có tiêu đề `## References`; mọi `[n]` trong thân tồn tại trong danh sách nguồn và mọi nguồn được trích ít nhất một lần; danh mục tham khảo có đúng một dòng cho mỗi nguồn, mỗi dòng chứa đúng một URL khớp với nguồn cùng số. Bộ kiểm tra mở rộng được trích dẫn nhóm như `[1, 2]`, `[1-3]` và bỏ qua `[n]` nằm trong khối mã hoặc liên kết Markdown.

### 2.6 Cổng kiểm tra tất định sau tác tử

Sau khi tác tử trưởng kết thúc, tập lệnh chính chạy lại một cổng kiểm tra trong sandbox trước khi lưu kết quả. Cổng này yêu cầu bộ hoàn thiện và bộ kiểm tra đều thành công, nhãn họ nguồn phải khớp với tiền tố URL (`arxiv` ứng với `https://arxiv.org/abs/`, `hf-*` ứng với `https://huggingface.co/papers/`), có ít nhất ba họ nguồn, và đủ bốn tiêu đề `TL;DR`, `Background`, `Trends and open problems`, `References`. Nếu không đạt, lỗi được trả lại cho tác tử để sửa. Nguyên tắc là các ràng buộc có thể kiểm tra bằng mã thì được kiểm tra bằng mã, thay vì chỉ dựa vào lời nhắc.

Khi lần chạy thất bại hoặc báo cáo rỗng hay tệp nguồn hỏng, chương trình thoát với mã khác 0 và không ghi tệp nào, để không để lại báo cáo rỗng trông như thành công.

### 2.7 Các điều chỉnh trong quá trình triển khai

- **Cấu hình mô hình.** Mô hình `gpt-5.6-luna` từ chối function tools ở điểm cuối chat completions khi có `reasoning_effort`. Cách xử lý là bật Responses API ngay trong tập lệnh chính, vì tệp tạo mô hình là tệp cho sẵn không được sửa.
- **Tiêu đề bắt buộc.** Lần chạy đầu của chủ đề tác tử LLM thiếu tiêu đề `Trends and open problems` do tác tử tự đặt tên khác. Kiểm tra tiêu đề được thêm vào cổng tất định và chủ đề này được chạy lại.
- **Gán sai nguồn.** Lần chạy đầu của chủ đề học tăng cường chứa một khẳng định gán cho trang S-GRPO nội dung mà trang đó không nêu. Lời nhắc của tác tử trưởng được bổ sung quy tắc chỉ gán khẳng định cho nguồn có ghi nhận chính điều đó, và số cặp khẳng định/URL mà `citation-checker` phải kiểm tăng từ 3 lên 5; sau đó chủ đề được chạy lại.
- **Ký tự xuống dòng.** Tệp danh sách chủ đề dùng CRLF khiến tên chủ đề có thêm ký tự `\r`. Lần chạy sai bị dừng ngay và chạy lại với tên sạch; không báo cáo sai nào được lưu.

Các báo cáo cuối cùng đều do hệ thống sinh ra và không được chỉnh sửa thủ công. Khi phát hiện lỗi, nguyên nhân được xử lý ở mã hoặc lời nhắc rồi chạy lại.

## 3. Phương pháp đánh giá

Đánh giá gồm ba lớp.

1. **Kiểm tra tự động:** số lần ủy quyền, họ nguồn, khớp nhãn họ với URL, tính hợp lệ của trích dẫn, đủ tiêu đề, và không có khóa trong git.
2. **Phân tích cấu trúc và nội dung:** đọc toàn bộ năm báo cáo, xem xét mức độ tổng hợp so sánh, độ cụ thể, độ mới của nguồn và chất lượng phần xu hướng.
3. **Kiểm chứng mẫu:** lấy ngẫu nhiên các câu có trích dẫn, mở nguồn và đối chiếu số liệu cụ thể. Trang `arxiv.org/abs` chỉ có tóm tắt nên số liệu trong thân bài phải đối chiếu qua bản HTML đầy đủ. Với tệp PDF mà công cụ đọc không được, kết quả được ghi là không xác minh được, không phải là đúng.

## 4. Kết quả định lượng

### 4.1 Hiệu năng và chi phí

| Chủ đề | Thời gian (giây) | Lần gọi tác tử con | Token lead (vào / ra) | Số nguồn | Số từ |
|---|---|---|---|---|---|
| Mô hình thế giới | 375,5 | 5 | 483.146 / 7.554 | 15 | 1.896 |
| RL cho suy luận LLM | 305,9 | 9 | 383.210 / 10.801 | 15 | 1.899 |
| Tác tử LLM và công cụ | 326,9 | 5 | 371.503 / 9.964 | 14 | 1.937 |
| Sinh video và đa phương thức | 281,2 | 5 | 159.304 / 6.446 | 22 | 1.995 |
| Suy luận hiệu quả và SLM | 236,6 | 5 | 266.291 / 6.908 | 17 | 2.020 |
| **Tổng** | **1.526 (khoảng 25,4 phút)** | | **1.663.454 / 41.673** | **83** | **9.747** |

Số token chỉ tính tin nhắn của tác tử trưởng. Token của các tác tử con, thường là phần lớn chi phí, không được thống kê, nên chi phí thật cao hơn đáng kể. Thời gian chỉ tính các lần chạy cuối cùng được giữ lại; các lần chạy bị thay thế hoặc bị dừng (mục 2.7) không được tính.

### 4.2 Phân bố họ nguồn

| Chủ đề | arxiv | hf-search | web | hf-daily | Nguồn không có ngày |
|---|---|---|---|---|---|
| Mô hình thế giới | 5 | 1 | 9 | 0 | 5 |
| RL cho suy luận LLM | 5 | 1 | 9 | 0 | 5 |
| Tác tử LLM và công cụ | 5 | 2 | 7 | 0 | 6 |
| Sinh video và đa phương thức | 9 | 1 | 12 | 0 | 9 |
| Suy luận hiệu quả và SLM | 6 | 1 | 10 | 0 | 5 |
| **Tổng (83 nguồn)** | **30** | **6** | **47** | **0** | **30** |

Họ `web` chiếm 47/83 nguồn. Theo quy ước của bài, nhãn `source` ghi công cụ đã trả về nguồn chứ không phải tên miền, nên nhiều bài arXiv mang nhãn `web` vì được tìm qua công cụ web. Họ `hf-daily` không xuất hiện ở chủ đề nào, và `hf-search` chỉ đóng góp 6 nguồn, thường một nguồn mỗi báo cáo. Yêu cầu ba họ nguồn vì thế được thỏa mãn về hình thức nhưng đóng góp của `hf-search` còn mỏng. Có 30/83 nguồn (36%) không có ngày công bố trong tệp nguồn, nên đánh giá độ mới chỉ chính xác một phần. Hai chủ đề cuối có 22 và 17 nguồn, vượt khoảng 10–15 nguồn mà lời nhắc yêu cầu; không bộ kiểm tra nào chặn điều này.

## 5. Phân tích nội dung năm bản khảo sát

### 5.1 Mô hình thế giới

**Luận điểm.** Mô hình thế giới được hiểu theo chức năng chứ không theo một kiến trúc cố định: đó là biểu diễn nội tại về cách môi trường tiến triển và hành động thay đổi môi trường ra sao, gồm bộ mã hóa quan sát, trạng thái tiềm ẩn và mô hình chuyển tiếp. Báo cáo so sánh ba họ phương pháp.

- **Mô hình động học tiềm ẩn** (PlaNet, Dreamer, DreamerV3, DayDreamer) đánh đổi độ trung thực điểm ảnh lấy tính hiệu quả của các lượt giả lập. DreamerV3 dùng một cấu hình cho hơn 150 tác vụ thuộc tám miền, và bài báo trên Nature mô tả việc thu thập kim cương trong Minecraft từ đầu mà không cần dữ liệu người hay giáo trình.
- **Mô hình sinh video** (Genie, Genie 2, RoboDreamer, WorldGPT, Genie Envisioner) cung cấp môi trường có thể điều khiển và con người quan sát được, nhưng độ chân thực thị giác không bảo đảm hệ quả vật lý hay khả năng thực thi hành động.
- **Phổ mô phỏng cho robot** trải từ bộ dự đoán gắn với chính sách, bộ mô phỏng học được, đến mô hình video sinh dữ liệu; hệ thống mô-đun dễ chẩn đoán còn hệ thống tích hợp đầu-cuối có thể nhanh hơn cho một vòng điều khiển cụ thể.

**Đánh giá.** Phần đánh giá là đóng góp đáng chú ý nhất. Các độ đo chung về video thưởng cho vẻ ngoài và độ tương đồng ngắn hạn, nhưng bỏ sót việc thay đổi hành động có làm thay đổi kết quả hay không. Báo cáo trình bày một thang bằng chứng: tính hợp lý thị giác, dự đoán có điều kiện theo hành động, tính hợp lệ vòng kín, dự đoán giá trị, mức nhất quán khi xếp hạng chính sách, độ cải thiện khi tối ưu, tính bị khai thác, và hiệu chuẩn độ bất định. Bài định vị được dẫn nêu rằng chỉ khoảng một chục công trình khảo sát báo cáo mức nhất quán xếp hạng với chính sách cố định, và gần như không công trình nào báo cáo khoảng cách khai thác. Với benchmark nhân quả What-If World, không mô hình video nào trong chín mô hình vượt 52% điểm ghép cặp.

**Xu hướng và vấn đề mở.** Ba xu hướng: mở rộng dữ liệu video và động học tiềm ẩn để tạo môi trường tương tác; bổ sung bộ giải mã hành động và vòng chính sách/đánh giá cho robot; chuyển benchmark từ chất lượng khung hình sang can thiệp và ích lợi quyết định. Các câu hỏi chưa giải quyết gồm mức độ trung thực thị giác thật sự cần thiết khi mục tiêu là đủ thông tin để điều khiển, cách giữ các biến vật lý thưa nhưng mang tính quyết định (tiếp xúc, ma sát, biến dạng), khả năng điều khiển khi sinh tự hồi quy dài, và cách biểu diễn độ bất định để bộ lập kế hoạch biết khi nào cần quay về thế giới thực.

**Hạn chế.** Có 5/15 nguồn không có ngày, gồm cả các nguồn nền tảng. Đoạn về PlaNet lặp lại cùng một ý hai lần. Câu về FOCUS dẫn bài khảo sát predictive coding cho robot (`[2]`), và việc bài đó có nêu FOCUS hay không chưa được kiểm tra. Các số liệu của WorldModelBench (67.000 nhãn người, sai số dự đoán vi phạm thấp hơn 9,9% so với GPT-4o) và WorldGPT (nhanh gấp 30 lần khuếch tán) chưa được xác minh.

### 5.2 Học tăng cường cho suy luận của LLM

**Luận điểm.** Học tăng cường cho suy luận được xem là một họ lựa chọn về gán tín dụng chứ không đơn thuần là "PPO áp dụng cho văn bản". Câu hỏi là phần thưởng gán cho cả chuỗi hay từng bước, và do ai kiểm chứng.

- **Giám sát kết quả và giám sát quá trình.** PRM800K cung cấp khoảng 800.000 nhãn bước trên 75.000 lời giải của 12.000 bài toán; mô hình giám sát quá trình giải đúng 78,2% một tập con MATH tiêu biểu. Giám sát quá trình định vị được lỗi, còn giám sát kết quả có thể chấp nhận đáp án đúng đạt được bằng lập luận sai.
- **Phần thưởng kiểm chứng được (RLVR).** Rẻ, tái lập được và dễ mở rộng trong toán và lập trình, nhưng chỉ chứng nhận điểm cuối. Khung RLVR được dẫn đề xuất CoT-Pass@K để chỉ tính mẫu có cả đáp án và chuỗi suy luận đúng.
- **Tối ưu chính sách.** GRPO của DeepSeekMath bỏ mạng giá trị bằng cách dùng điểm trung bình của nhóm mẫu làm đường cơ sở; huấn luyện trên khoảng 144K câu hỏi nâng DeepSeekMath-Instruct 7B từ 82,9% lên 88,2% (GSM8K) và từ 46,8% lên 51,7% (MATH). Các cách tiếp cận ngoại tuyến như ReST và STaR tái sử dụng dữ liệu và dễ gỡ lỗi hơn nhưng có thể khám phá kém các nghiệm xác suất thấp.
- **Mở rộng.** DeepSeek-R1 báo cáo 79,8% AIME, 97,3% MATH-500, Elo Codeforces 2.029 và 71,5% GPQA Diamond. Open-Reasoner-Zero cho thấy PPO nguyên bản với phần thưởng theo luật có thể đạt kết quả tương đương với số bước huấn luyện bằng một phần mười. SWE-RL và OpenRFT đưa phương pháp sang phần mềm và khoa học.

**Chế độ lỗi.** Ba nhóm vấn đề được nhấn mạnh. Thứ nhất là sai lệch đo lường: chênh ngân sách thử, tăng số lần thử, trôi hiệu chuẩn và nhiễm dữ liệu. Thứ hai là co hẹp phạm vi nghiệm: nghiên cứu "Invisible Leash" cho rằng RLVR khuếch đại các đầu ra thưởng cao vốn đã có trong mô hình gốc; với ProRL-1.5B, tỷ lệ mất so với được các lời giải đúng là khoảng 3,6:1 (175 so với 48), và pass@8192 trên AIME2024 là 93,3% với mô hình gốc so với 83,3% sau RL. Thứ ba là khai thác bộ kiểm chứng: mô hình liệt kê nhãn hoặc lợi dụng bộ kiểm chứng ngoại diên thay vì học quy tắc bất biến, và kiểm thử đẳng cấu phát hiện được điều này.

**Xu hướng và vấn đề mở.** Lĩnh vực chuyển từ câu hỏi liệu RL có cải thiện một benchmark hay không sang câu hỏi phần thưởng đã chọn lọc hành vi nào. Huấn luyện ngày càng có tính mô-đun: khởi động lạnh, tự huấn luyện, tối ưu nhóm hoặc PPO, và bộ kiểm chứng theo miền. Vấn đề mở gồm khi nào phần thưởng chỉ dựa trên đáp án thực sự cải thiện quá trình suy luận thay vì chỉ tương quan với nó, cách giữ tính đa dạng khi tăng pass@1, cách xử lý độ bất định và hiệu chuẩn như chỉ số hạng nhất, và cách sàng lọc dữ liệu thưởng khỏi nhiễm và khai thác.

**Hạn chế.** Số liệu của DeepSeek-R1-Zero (AIME 2024 pass@1 tăng từ 15,6% lên 71,0%) lệch so với bản arXiv hiện hành, nơi con số là 77,9%; báo cáo không nêu phiên bản. Số liệu OpenRFT (cải thiện trung bình 11% trên tám tác vụ SciKnowEval với 100 mẫu mỗi tác vụ) chưa xác minh được do tệp PDF không đọc được. Một số ngày trong danh mục tham khảo là ngày phiên bản chứ không phải ngày công bố gốc (DeepSeekMath ghi 2024-04-27).

### 5.3 Tác tử LLM và sử dụng công cụ

**Luận điểm.** Tác tử LLM là hệ thống điều khiển bằng phản hồi: nhận trạng thái, suy luận về mục tiêu, hành động qua công cụ hoặc môi trường, rồi dùng kết quả để điều chỉnh bước tiếp theo. Trục thiết kế trung tâm là đặt quyền kiểm soát ở đâu.

- **Bộ định tuyến mô-đun** (MRKL) giao việc chính xác cho các chuyên gia tượng trưng nhưng bị giới hạn bởi độ phủ các mô-đun.
- **Học gọi API từ văn bản** (Toolformer) giữ lại các lời gọi làm giảm perplexity của token tương lai; mô hình 6,7B tham số cải thiện 11,7, 5,2 và 18,6 điểm trên các phần của LAMA so với đường cơ sở cùng cỡ.
- **Nền tảng hóa theo khả năng thực thi** (SayCan) kết hợp mức hữu ích về ngữ nghĩa với xác suất thành công trong trạng thái hiện tại; trên 101 tác vụ nhà bếp thực tế, hiệu năng gần gấp đôi so với đường cơ sở không nền tảng hóa.

Về lập kế hoạch và bộ nhớ, ReAct xen kẽ suy luận và hành động, tạo vết đọc được nhưng một lựa chọn sai sớm có thể ràng buộc mọi bước sau; LATS dùng tìm kiếm cây Monte Carlo để quay lui, đổi lại thêm chi phí gọi mô hình; Reflexion lưu phản hồi dạng ngôn ngữ trong bộ đệm theo từng tập nhưng không vượt trội đáng kể so với ReAct trên WebShop khi phản chiếu mang tính chung chung.

**Benchmark thực tế.** Khoảng cách giữa gọi công cụ cục bộ và hiệu năng tự chủ là bằng chứng rõ nhất. Trên WebArena, tác tử GPT-4 tốt nhất đạt 14,41% thành công đầu-cuối so với 78,24% của con người. Trên OSWorld, mô hình tốt nhất đạt 12,24% so với mức trên 72,36% của con người, và quy trình đa ứng dụng chỉ đạt 6,57%. Điều này gợi ý lập kế hoạch và điều hướng là nút thắt ngay cả khi việc dùng công cụ cục bộ khá tốt.

**Độ tin cậy và an toàn.** Độ chính xác đáp án cuối che khuất nhiều lỗi. Nghiên cứu kiểm toán 14.750 vết thực thi từ 13 tác tử cho thấy bộ đánh giá dựa trên chuỗi con chỉ đồng thuận với người ở mức ngẫu nhiên (kappa 0,049) và việc bịa ra lời gọi công cụ xuất hiện ở 37,5% vết của một mô hình trong nghiên cứu. Agent-SafetyBench cho thấy không tác tử nào trong 16 tác tử vượt 60 điểm an toàn.

**Xu hướng và vấn đề mở.** Đánh giá chuyển sang tác vụ dài, đa phương thức, đa ứng dụng và có xét an toàn. Năm vấn đề mở: lập kế hoạch và điều hướng; kiểm thử nhất quán dài hạn cho bộ nhớ; an toàn mang tính dự phòng và theo ngữ cảnh; độ tin cậy của chính bộ đánh giá; và báo cáo chất lượng tác tử như một vectơ (hoàn thành, chi phí, hiệu quả, độ tin cậy, phục hồi, an toàn) chứ không phải một độ chính xác duy nhất.

**Hạn chế.** Trong phần bộ nhớ, các khẳng định về Generative Agents (25 tác tử, điểm TrueSkill 29,89 so với 21,21) được dẫn `[4]`, vốn là bài Reflexion, trong khi danh mục tham khảo không chứa bài Generative Agents. Đây là dấu hiệu rõ rệt của việc gán sai nguồn; nghi vấn này chưa được kiểm tra trực tiếp bằng cách mở nguồn. Chủ đề này cũng có ít nguồn mới nhất trong dữ liệu có ngày (chỉ một nguồn năm 2025, và 6/14 nguồn không có ngày). Các số liệu của LATS, SWE-bench Verified, AgentBench, ToolEmu và Agent-SafetyBench chưa được xác minh.

### 5.4 Sinh video và đa phương thức

**Luận điểm.** Sinh video chuyển từ dự đoán token rời rạc tự hồi quy sang khuếch tán tiềm ẩn kết hợp Transformer coi các mảnh không-thời gian là token.

- **Tự hồi quy rời rạc.** VideoGPT nén video bằng VQ-VAE 3D và mô hình hóa các mã bằng Transformer kiểu GPT. VideoPoet mở rộng sang hình ảnh, video, văn bản và âm thanh, đạt CLIPSIM 0,3049 và FVD 213 trên MSR-VTT trong thiết lập zero-shot. Hướng này thống nhất mục tiêu hợp lý nhưng giải mã tuần tự tốn kém.
- **Khuếch tán tiềm ẩn.** Khuếch tán xử lý song song và điều khiển liên tục tốt hơn, nhưng cần nhiều bước khử nhiễu và chú ý tốn bộ nhớ. Latte, Sora và Open-Sora phân rã chú ý không gian và thời gian; Open-Sora báo cáo 79,76% tổng điểm VBench ở độ phân giải 240p, 2 giây.
- **Hợp nhất đa phương thức.** Có hai nghĩa của "hợp nhất": không gian token dùng chung (VideoPoet) và hệ thống mô-đun lấy LLM làm trung tâm cùng các bộ giải mã chuyên biệt (NExT-GPT, chỉ tinh chỉnh khoảng 1% tham số). Mô-đun hóa giảm chi phí huấn luyện nhưng phụ thuộc vào nhiều thành phần tiền huấn luyện và sự căn chỉnh giao diện.
- **Kiểm soát và âm thanh.** Điều khiển camera, ảnh tham chiếu, khung hình khóa, và âm thanh đồng bộ (MMAudio) mở rộng điều kiện sinh ra ngoài lời nhắc văn bản.

**Mở rộng và hiệu quả.** Chi phí tăng nhanh theo số điểm ảnh, số khung và số bước khử nhiễu. Imagen Video dùng chuỗi mô hình siêu phân giải để đạt khoảng 5,3 giây ở 1280×768; LinGen đề xuất xử lý độ phức tạp tuyến tính nhằm sinh video dài một phút trên một GPU.

**Đánh giá và an toàn.** Các độ đo phân phối như FID và FVD cùng điểm dựa trên CLIP không phát hiện được vật thể biến mất hay va chạm bất khả thi. TC-Bench cho thấy phần lớn trình sinh đạt dưới 20% thay đổi thành phần được yêu cầu. DynamicEval, với 45.000 chú thích người trên 3.000 video, cho thấy các lỗi của độ đo chuyển động mượt của VBench khi có che khuất và chuyển động camera. Về an toàn, T2VSafetyBench và SAFESORA nhấn mạnh rằng các khung hình vô hại có thể tạo nội dung có hại qua tính liên tục thời gian.

**Xu hướng và vấn đề mở.** Biểu diễn mảnh có thể mở rộng, huấn luyện chung ảnh và video, chú ý phân rã hoặc tuyến tính, điều khiển phong phú và sinh âm thanh–hình ảnh gốc. Năng lực không đồng đều: thời lượng và độ phân giải cải thiện nhanh hơn suy luận nhân quả, hợp thành thời gian và đồng bộ âm thanh. Vấn đề mở gồm khả năng học trạng thái và quan hệ vật lý bền vững, biểu diễn tối ưu giữa không gian token chung và ngăn xếp mô-đun, đánh giá ổn định với camera và che khuất mà vẫn rẻ, và các ràng buộc về nguồn gốc dữ liệu huấn luyện, giấy phép và ghi nhớ nội dung.

**Hạn chế.** Đây là chủ đề có nhiều nguồn nhất (22) và nhiều nguồn không ngày nhất (9/22). Một số nguồn là trang sản phẩm (Runway Gen-3 Alpha, Veo 3.1, Imagen Video), nên các khẳng định tính năng phản ánh mô tả của nhà cung cấp chứ không phải kết quả đã bình duyệt. Hai mục tham khảo (`[4]` và `[5]`) cùng thuộc bài VideoPoet với hai URL khác nhau, nên có trùng lặp thực chất. Phần lớn số liệu (VBench của Open-Sora, CLIPSIM/FVD của VideoPoet, FID/FAD của NExT-GPT, T2VSafetyBench, SAFESORA) chưa được xác minh.

### 5.5 Suy luận hiệu quả và mô hình ngôn ngữ nhỏ

**Luận điểm.** Mô hình ngôn ngữ nhỏ được định nghĩa theo khả năng triển khai chứ không chỉ theo số tham số: khoảng 100 triệu đến 5 tỷ tham số cho mô hình chỉ giải mã, với ràng buộc bộ nhớ, độ trễ và năng lượng của thiết bị mục tiêu. Suy luận có hai điểm nghẽn khác nhau: giai đoạn prefill thiên về tính toán và quyết định độ trễ token đầu tiên, còn giai đoạn giải mã thường bị giới hạn bởi bộ nhớ và quyết định độ trễ mỗi token.

**Nén mô hình trước khi phục vụ.**

- **Chưng cất** chuyển hành vi thay vì chỉ xóa tham số. TinyBERT chưng cất embedding, trạng thái ẩn, ma trận chú ý và logits, nhỏ hơn 7,5 lần và nhanh hơn 9,4 lần so với BERT-base; MobileBERT nhỏ hơn 4,3 lần và nhanh hơn 5,5 lần, với độ trễ 62 ms trên Pixel 4.
- **Lượng tử hóa** gồm sau huấn luyện và có huấn luyện nhận biết lượng tử; các lựa chọn chính là chỉ trọng số, trọng số cùng kích hoạt, và KV-cache. Biểu diễn nhỏ hơn không bảo đảm tăng tốc tương ứng: đo trên Phi-1.5 cho thấy giảm ít nhất 25% độ trễ prefill ở lời nhắc ngắn, nhưng chỉ giảm 13% ở cấu hình Q4_K_M tốt nhất với lời nhắc 50 token.
- **Cắt tỉa, chia sẻ và phân rã hạng thấp** giảm dư thừa, nhưng cắt tỉa không có cấu trúc hiếm khi tăng tốc trên phần cứng thông dụng, và chia sẻ tham số không nhất thiết giảm số tầng Transformer tuần tự.

**Hệ thống chạy.** Sau khi nén, tối ưu hóa tập trung vào công việc lặp lại và di chuyển bộ nhớ: tái sử dụng KV-cache giữa các lượt hội thoại; QuantSpec kết hợp giải mã tự suy đoán với KV-cache 4 bit, báo cáo tốc độ tăng khoảng 2,5 lần; TinyServe chọn trang KV theo truy vấn, báo cáo tăng tốc đến 3,4 lần; SpecMemo quản lý bộ nhớ giải mã suy đoán, giữ 96% thông lượng và giảm 65% bộ nhớ sinh trong thiết lập MT-Bench trên một GPU.

**Đánh giá.** Báo cáo nhấn mạnh rằng FLOPs và token mỗi giây là đại diện kém cho trải nghiệm người dùng. Efficiency Pentathlon đo thông lượng, độ trễ, bộ nhớ, số tham số và năng lượng trên phần cứng kiểm soát. ML.ENERGY dựng biên Pareto thời gian–năng lượng; trong một ví dụ chatbot, một cấu hình với 77 ms mỗi token giảm 44% năng lượng so với cấu hình tối thiểu hóa độ trễ trong khi vẫn đáp ứng ngưỡng 100 ms. HELM bao quát độ chính xác, hiệu chuẩn, độ bền vững, công bằng, thiên lệch, độc hại và hiệu quả, đồng thời cho thấy độ phủ không đầy đủ làm sai lệch so sánh. Một nghiên cứu trên 63 mô hình nhỏ từ 15 họ ghi nhận 47,6% có tỷ lệ tấn công thành công trên 40% với truy vấn có hại trực tiếp, và quy mô tham số không đủ để dự đoán độ an toàn.

**Kết luận của chủ đề.** Báo cáo đi đến một phát biểu có điều kiện: chọn mô hình nhỏ nhất đáp ứng yêu cầu chất lượng và độ tin cậy, rồi tối ưu toàn bộ đường thực thi. Chưng cất và kiến trúc xác lập điểm cân bằng giữa dung lượng và chất lượng; lượng tử hóa và độ thưa có cấu trúc giúp mô hình vừa bộ nhớ; bộ đệm và giải mã suy đoán quyết định hành vi ngữ cảnh dài; đánh giá đa chỉ số có kiểm soát quyết định liệu hiệu quả là thật.

**Vấn đề mở.** Quy luật mở rộng có nhận biết triển khai (kết hợp chất lượng, số tham số, dữ liệu, bộ nhớ thiết bị và tính toán); benchmark dựa trên phân phối khối lượng công việc và thông lượng hữu ích (goodput) thay vì thông lượng số học; đánh giá độ bền vững và quyền riêng tư ngay trên thiết bị.

**Hạn chế.** Báo cáo có ít phần chủ đề nhất (ba phần). Một số khẳng định dẫn nguồn chưa chắc phù hợp, ví dụ nhận định về chia sẻ tham số dẫn `[13]` (TinyBERT) mà việc bài đó nêu điều này chưa được kiểm tra. Kết quả SpecMemo trên Llama-2-70B không thuộc phạm vi mô hình nhỏ và được báo cáo tự ghi nhận như vậy. Phần lớn con số tăng tốc, tiết kiệm bộ nhớ và năng lượng chưa được xác minh; ngày của một số nguồn là ngày phiên bản (HELM ghi 2023-10-01).

## 6. Kiểm chứng trích dẫn

### 6.1 Kết quả đối chiếu mẫu

| Mệnh đề | Nguồn | Kết quả |
|---|---|---|
| ProRL-1.5B: tỷ lệ 3,6:1 (175 so với 48); pass@8192 trên AIME2024 là 93,3% so với 83,3% | Invisible Leash (HTML) | Khớp |
| DeepSeekMath: GSM8K 82,9 → 88,2; MATH 46,8 → 51,7; khoảng 144K câu hỏi; độ dài tối đa 1.024; tốc độ học 1e-6; hệ số KL 0,04 | DeepSeekMath (HTML) | Khớp; "64 mẫu mỗi câu hỏi" không xác nhận được vì lỗi hiển thị |
| DeepSeek-R1: 79,8; 97,3; 2.029; 71,5; biểu quyết đa số 86,7% | DeepSeek-R1 (HTML) | Khớp |
| DeepSeek-R1-Zero: AIME 2024 pass@1 15,6% → 71,0% | DeepSeek-R1 (HTML) | Lệch: bản hiện hành ghi 77,9% |
| OpenRFT: 11% trên 8 tác vụ SciKnowEval với 100 mẫu mỗi tác vụ | OpenRFT (PDF) | Không xác minh được |
| OSWorld: trên 72,36% (người) so với 12,24% (mô hình tốt nhất) | OSWorld (tóm tắt) | Khớp; số của người là cận dưới, trang không nêu tên mô hình |
| TC-Bench: dưới 20% thay đổi thành phần | TC-Bench (tóm tắt) | Khớp |
| DynamicEval: 45.000 chú thích trên 3.000 video; cải thiện hơn 2 điểm phần trăm | DynamicEval (tóm tắt) | Khớp; mức cải thiện thuộc bộ độ đo đề xuất nói chung, chưa tách riêng thành phần nhận biết đối tượng |

Với phiên bản báo cáo học tăng cường đã bị thay thế (mục 2.7), Open-RS (46,7% AIME24, 80% AMC23, bốn GPU A40, 7.000 mẫu, 42 USD) khớp với tóm tắt (tên "Open-RS3" không xuất hiện ở trang tóm tắt), còn khẳng định về "Guide… tự chưng cất" gán cho trang S-GRPO không được trang đó ủng hộ.

### 6.2 Phân loại lỗi quan sát được

1. **Gán sai nguồn.** Khẳng định đúng hoặc nói về một bài có thật nhưng trích dẫn trỏ tới bài khác (S-GRPO/Guide trong phiên bản cũ; nghi vấn Generative Agents/Reflexion ở chủ đề tác tử). Đây là dạng lỗi nguy hiểm nhất vì trông hợp lệ ở mọi kiểm tra cấu trúc.
2. **Lệch phiên bản.** Số liệu đúng với một phiên bản của bài báo nhưng khác phiên bản hiện hành (R1-Zero 71,0% so với 77,9%).
3. **Ngày là ngày phiên bản.** Cột ngày trong danh mục tham khảo nhiều khi là ngày của phiên bản chứ không phải ngày công bố gốc.
4. **Trùng lặp nguồn.** Cùng một công trình xuất hiện hai lần với hai URL (VideoPoet).
5. **Nguồn thương mại.** Một số khẳng định về tính năng dựa trên trang giới thiệu sản phẩm.

### 6.3 Giới hạn của việc kiểm chứng

Cỡ mẫu khoảng 16 mệnh đề trên hàng trăm khẳng định có trích dẫn, và lệch về các mệnh đề có số liệu nổi bật. Các khẳng định mô tả định tính hầu như chưa được kiểm tra. Bộ kiểm tra trích dẫn chỉ bảo đảm tính nhất quán cấu trúc và không xác nhận được nguồn có nói điều được trích. Không phải toàn bộ 83 URL đã được mở. Kết quả mẫu vì vậy là bằng chứng thống kê yếu: nó cho thấy hệ thống thường chính xác ở các số liệu then chốt, đồng thời chứng minh rằng các lỗi gán nguồn có thể tồn tại mà kiểm tra tự động không bắt được.

## 7. Thảo luận

**Hiệu quả của phân rã và song song hóa.** Cả năm chủ đề đều có từ 5 lần ủy quyền trở lên, thời gian chạy từ khoảng 4 đến 6 phút, và mức độ tổng hợp so sánh tốt: các phần chủ đề được tổ chức theo trục đánh đổi thay vì liệt kê từng bài. Chất lượng này phụ thuộc vào lời nhắc yêu cầu đối chiếu hướng tiếp cận và vào việc tác tử trưởng đọc ghi chú trước khi viết.

**Xử lý tất định sau mô hình đáng tin hơn lời nhắc.** Hai trong số các lỗi phát hiện (tiêu đề thiếu và nhãn họ nguồn sai) được chặn triệt để bằng cổng kiểm tra bằng mã, trong khi lỗi gán sai nguồn, vốn cần hiểu ngữ nghĩa, chỉ được giảm bằng lời nhắc và kiểm tra mẫu và vì vậy không thể bảo đảm. Điều này phù hợp nhận xét rằng mọi ràng buộc kiểm tra được bằng mã nên được kiểm tra bằng mã.

**Tính ngẫu nhiên.** Cùng một mã có thể cho báo cáo hợp lệ ở lần này và lỗi ở lần sau. Chạy lại sau khi sửa lời nhắc xử lý được lỗi cụ thể đã quan sát nhưng không bảo đảm loại bỏ các lỗi tương tự; báo cáo học tăng cường chạy lại là một văn bản hoàn toàn mới với số liệu khác, và chỉ một phần số liệu mới được kiểm.

**Các xu hướng chung giữa năm chủ đề.**

1. Đánh giá là nút thắt chính. Ở mọi chủ đề, chỉ số đơn lẻ (chất lượng khung hình, pass@1, FLOPs, độ chính xác đáp án cuối) che khuất các lỗi quan trọng: nhân quả, khai thác phần thưởng, khả năng phục hồi, hợp thành theo thời gian, độ trễ đuôi và năng lượng.
2. Khoảng cách giữa năng lực cục bộ và hiệu năng đầu-cuối. Tác tử gọi công cụ đúng ở bước đơn nhưng thất bại ở tác vụ dài; video đẹp nhưng sai vật lý; mô hình nén chưa chắc nhanh hơn trên phần cứng thật.
3. Thiết kế hỗn hợp theo mô-đun trở thành chuẩn: RL kết hợp khởi động lạnh, tự huấn luyện và bộ kiểm chứng; sinh đa phương thức kết hợp LLM và bộ giải mã chuyên biệt; suy luận hiệu quả kết hợp lượng tử hóa, bộ đệm và giải mã suy đoán.
4. An toàn và độ tin cậy là ràng buộc thiết kế chứ không phải phần bổ sung: khai thác phần thưởng, an toàn công cụ, an toàn video theo thời gian, an toàn của mô hình nhỏ.

## 8. Hạn chế

- **Phạm vi kiểm chứng.** Chỉ một phần rất nhỏ khẳng định được đối chiếu với nguồn (mục 6.3).
- **Cấu trúc dữ liệu nguồn.** 36% nguồn thiếu ngày công bố; họ `web` chiếm đa số và `hf-search` đóng góp ít, nên tính đa dạng của nguồn chỉ đạt ở mức hình thức. Họ `hf-daily` chưa từng được dùng.
- **Chi phí không đầy đủ.** Token của tác tử con không được thống kê; các lần chạy bị thay thế hoặc bị dừng không được tính vào thời gian và chi phí.
- **Phụ thuộc vào một mô hình.** Mọi kết quả sinh ra từ một mô hình duy nhất với một bộ lời nhắc; chưa khảo sát độ nhạy với mô hình khác hay với các lần chạy lặp lại.
- **Bộ kiểm tra trích dẫn.** Chỉ đảm bảo tính nhất quán cấu trúc; việc gán sai nguồn vẫn lọt qua.
- **Độ mới của nguồn.** Ở chủ đề tác tử LLM, phần dữ liệu có ngày chỉ có một nguồn năm 2025; một số nguồn không ngày có thể mới nhưng không chứng minh được.
- **Nghi vấn chưa xác minh.** Khẳng định về Generative Agents trong chủ đề tác tử LLM (mục 5.3) cần đối chiếu trực tiếp với bài báo gốc trước khi dựa vào phần đó của báo cáo.

## 9. Kết luận

Hệ thống đạt mục tiêu thiết kế: từ một chủ đề, nó lập kế hoạch, ủy quyền song song, truy cập ba họ nguồn, và tạo báo cáo có cấu trúc, có trích dẫn, vượt qua kiểm tra tự động, trong khoảng 4–6 phút cho mỗi chủ đề. Về nội dung, năm bản khảo sát tổng hợp được các hướng tiếp cận theo trục so sánh và nêu được xu hướng cùng các vấn đề mở cụ thể. Phần lớn số liệu được kiểm mẫu khớp với nguồn.

Tuy vậy, độ tin cậy của một báo cáo tự động không thể được bảo đảm bằng kiểm tra cấu trúc. Các lỗi gán sai nguồn, lệch phiên bản và nguồn thương mại vẫn xuất hiện và chỉ có thể phát hiện bằng đối chiếu nguồn. Vì vậy các báo cáo này nên được xem là bản thảo khảo sát có trích dẫn cần được kiểm tra trước khi dùng làm căn cứ, chứ không phải tài liệu đã thẩm định. Hướng cải tiến hợp lý là mở rộng bước kiểm tra mẫu tự động bằng tác tử đối chiếu, bắt buộc ghi phiên bản bài báo cho mọi số liệu, và bổ sung ngày công bố cho mọi nguồn.

## Phụ lục A. Đầu ra của hệ thống

| Chủ đề | Tệp báo cáo |
|---|---|
| Mô hình thế giới | `reports/survey-about-world-model.md` |
| RL cho suy luận LLM | `reports/survey-about-reinforcement-learning-for-llm-reasoning.md` |
| Tác tử LLM và công cụ | `reports/survey-about-llm-agents-and-tool-use.md` |
| Sinh video và đa phương thức | `reports/survey-about-video-and-multimodal-generation.md` |
| Suy luận hiệu quả và SLM | `reports/survey-about-efficient-inference-and-small-language-models.md` |

Mỗi báo cáo đi kèm `<slug>.sources.json` (danh sách nguồn có cấu trúc) và `<slug>.meta.json` (chủ đề, mô hình, thời gian, số lần ủy quyền, số lần gọi công cụ, token, số nguồn, các họ nguồn).

## Phụ lục B. Tái lập kết quả

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # điền khóa LLM, DAYTONA_API_KEY, EXA_API_KEY
python research.py "survey about world model"
python check_citations.py reports/survey-about-world-model.md reports/survey-about-world-model.sources.json
python self_check.py
```

Kết quả có tính ngẫu nhiên: cùng một mã có thể cho báo cáo khác nhau giữa các lần chạy.
