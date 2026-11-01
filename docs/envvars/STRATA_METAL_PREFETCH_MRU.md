# `STRATA_METAL_PREFETCH_MRU`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは clean（`## main...origin/main`）。外部ライブラリの環境変数の動作は対象外。

## 役割

Metal engine の SSD expert streaming で、decode window の予測先読みが新たに読み込む expert slot を slot LRU の前（優先して残す側）と後ろ（追い出し候補側）のどちらへ置くかを決めます。有効時は前、無効時は後ろです（`metal/src/engine/stream.cpp:575-615`）。

この設定は先読みそのものを有効にするスイッチではありません。先読みの有無は主に `STRATA_METAL_PREFETCH` が決めます。`STRATA_METAL_PREFETCH2` による layer + 2 の先読みでも、実際に `ahead()` が呼ばれれば同じ slot 配置設定が使われます（`metal/src/engine/stream.cpp:157-160,711-714`）。

## 値と判定

`ExpertStream::open()` は共通 helper `env_int(name, default)` で読みます。helper は環境変数が未設定、または空文字なら既定値を返し、それ以外は `std::atoi` の戻り値を使います。戻り値が 0 以外なら有効です（`metal/src/engine/stream.cpp:27-30,154-160`）。

| 入力 | 判定 |
|---|---|
| 未設定、空文字 | expert の大きさによる既定値（下記） |
| `0`、数値として 0 になる文字列 | 無効 |
| 非ゼロ整数（正負を含む） | 有効 |
| 数字で始まらない非空文字列（例: `true`） | `atoi` が 0 を返すため無効 |
| 数字の後ろに文字が続く文字列（例: `2x`） | 数値部分を `atoi` が変換し、非ゼロなら有効 |

文字列全体の検証、範囲チェック、clamp はありません。空白や符号などの扱いは `atoi` に委ねられます。整数範囲を超える入力の結果はこのコードで定義・検査されていません。

未設定または空文字で使われる既定値は、全 48 layer の expert 1 個あたりの gate/up/down 合計サイズの平均が 1,500,000 bytes より大きい場合は `0`、それ以外は `1` です。境界値ちょうどは「大きい」側ではありません（`metal/src/engine/stream.cpp:154-160`）。

## 有効になる条件

この値が処理に影響するには、次の条件が必要です。

- macOS 向け Metal engine がビルドされていること。Metal CMake project は Apple 以外では停止し、engine の生成は `STRATA_METAL_ENGINE` が ON の場合です（`metal/CMakeLists.txt:1-2,13-18,71-77,110-130`）。
- Window が expert streaming を使うこと。`STRATA_METAL_STREAM=1` は streaming を強制し、`=0` は無効にします。それ以外（未設定を含む）は `ExpertStream::wanted()` の容量判定に従います。streaming でなければ `ExpertStream::open()` は呼ばれず、この変数は読み取られません（`metal/src/engine/stream.cpp:33-48`, `metal/src/engine/window.cpp:541-548`）。
- その Window が Qwen3.8-Flash-Next の対応 geometry（48 layers 等）を通過して初期化されること（`metal/src/engine/window.cpp:524-533`）。
- decode の layer handshake で予測 logits が渡され、先読みが発行されること。通常の layer + 1 先読みは `STRATA_METAL_PREFETCH` の値が正であることが前提です。

  `STRATA_METAL_PREFETCH` は stream 側で `env_int` により読み取られ、未設定・空文字なら `big` に応じて 6 または 10、それ以外は `atoi` の値です。一方 window 側では別途 `getenv` と `atoi` で `st_pred_` を決め、設定値が存在して `atoi(e) <= 0` なら予測バッファを作りません。このため、空文字や不正文字列は stream 側の `pre_k_` 既定値だけを見ると正に見える場合でも、実際には window 側の予測を止めます。`pre_k_ <= 0` も先読みを止めます。`STRATA_METAL_PREFETCH2` が正でも、layer + 2 用予測バッファは `st_pred_` が true で `ahead2() > 0` のときだけ作られます（`metal/src/engine/stream.cpp:154-160`, `metal/src/engine/window.cpp:728-731`）。

CLI 引数による `STRATA_METAL_PREFETCH_MRU` の上書き箇所は見つかりません。値は `ExpertStream::open()` で読み取られ、その Window の `pre_mru_` に保持されます。実行中の環境変更を再読込するコードはありません。新しい Window の初期化時にはその時点の環境値が読まれます（`metal/src/engine/window.cpp:543-548`, `metal/src/engine/stream.cpp:157-163`）。

prompt chunk（`T > 8`）では layer + 1 の未 resident experts をまとめて queue に追加し、その場で戻るため、decode の `ahead()` 内にある `pre_mru_` 分岐を通りません（`metal/src/engine/stream.cpp:617-620,690-714`）。

## 実行時の詳細

通常の decode では、各 layer の routed experts を確保した後、次 layer の router logits から各 token の上位 `pre_k_` experts を選び、expert がまだ arena にない場合に空き victim slot へ読み込みを queue します。新規に queue した slot は `pre_mru_ != 0` なら `lru_front()`、0 なら `lru_back()` へ置かれます（`metal/src/engine/stream.cpp:575-615`）。layer + 2 先読みも同じ helper を使います（`metal/src/engine/stream.cpp:711-714`）。

`victim()` は各 size class の LRU tail から、読み込み中でなく現在の handshake で pin されていない slot を探します。そのためこの設定は、新たに先読みした expert が次の eviction で選ばれやすいかを変えます。予測対象がすでに arena にある場合は `ahead()` が設定にかかわらず `lru_front()` へ移動します。また decode の本処理で expert が見つかった場合も前へ移動します（`metal/src/engine/stream.cpp:256-269,598-610,649-669`）。この変数自体が読み込みの成否、予測内容、arena 容量を変更する分岐はありません。

## ログと失敗経路

この変数の値を表示する専用ログ、無効値への警告、値に起因する終了経路はありません。初期化後の arena ログは `read-ahead top` の数（`STRATA_METAL_PREFETCH` 側の深さ）を表示しますが、MRU 設定値そのものは表示しません（`metal/src/engine/stream.cpp:541-544`）。stream 終了時には先読み hit / miss / cancel などの集計が stderr に出ますが、MRU の ON/OFF は出ません（`metal/src/engine/window.cpp:1430-1432`, `metal/src/engine/stream.cpp:803-821`）。

streaming 初期化や読み込みには別の失敗経路があります。たとえば model geometry 不一致は Window 初期化を失敗させ、arena が 4 buffer を超える場合や mmap に失敗する場合は `err` を返します（`metal/src/engine/window.cpp:530-533`, `metal/src/engine/stream.cpp:447-460`）。実行中に expert slot が得られない場合、stderr に `strata metal stream: no free slot (layer %d)\n` を出して exit code 6 で終了します。expert 読み込み失敗も stderr に layer/expert を出して exit code 6 です。これらは本変数を値検証する経路ではありません（`metal/src/engine/stream.cpp:286-303,671-674`）。

## 根拠

- 変数の全直接参照は `metal/src/engine/stream.cpp:160` の 1 箇所です。環境読み取り helper は同ファイル内の `env_int`（`metal/src/engine/stream.cpp:27-30`）で、動的な名前渡し先や他の backend の同名参照はありません。
- stream の自動選択と強制指定: `metal/src/engine/stream.cpp:33-48`、Window 初期化での選択: `metal/src/engine/window.cpp:541-548`。
- `STRATA_METAL_PREFETCH` と予測バッファの条件: `metal/src/engine/stream.cpp:154-160,711-714`、`metal/src/engine/window.cpp:723-731`。
- LRU victim と先読み slot の配置: `metal/src/engine/stream.cpp:245-269,575-615`。
