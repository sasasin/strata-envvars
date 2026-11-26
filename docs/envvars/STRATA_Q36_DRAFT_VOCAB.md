# `STRATA_Q36_DRAFT_VOCAB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Qwen3.6 専用 engine の MTP draft head が候補にする語彙行数を指定する。正の値が高速 draft head の条件を満たすと、出力行列の先頭 N 行（低い token ID 側）だけで draft token を選ぶ。候補を絞っても、通常モデルによる verify が採用・拒否を決め、最終的な greedy token は変えない。高速 head の条件を満たさない値・モデルでは全語彙の head 計算へ fallback する（`engine/src/qwen35/q36_engine.cu:3054-3077`）。

この変数を読むのは `strata::qwen35::run` の CUDA/HIP 用 Qwen3.6 engine である。`strata` の通常モデル起動は build に `STRATA_HAVE_QWEN35` があり、GGUF の family が `Qwen35Moe` のときこの engine に振り分ける（`engine/src/program/generate.cpp:3804-3818`）。

## 値と判定

`--draft-vocab` の値が負のままで、かつ環境変数が設定されている場合に `std::atoi` で変換する。従って、環境変数が未設定なら `draft_vocab` は初期値 `-1` のまま `std::max(0, ...)` により 0 となる。空文字も `atoi` の結果は 0。0 以下は `draft_n <= 0` により全語彙の head を使う。CLI の `--draft-vocab` が 0 以上ならそちらが優先され、環境変数は読み取られない。CLI 値が負なら環境変数の fallback が行われる（`engine/src/qwen35/q36_engine.cu:5345,5380,5557-5558`）。

| 判定条件 | 例 | 結果 |
|---|---|---|
| 環境変数が未設定、または変換結果が 0 以下 | unset、空文字、`0`、`-8`、`true` | `draft_n` は 0。全語彙で head を計算する |
| 正数で、高速 head の形状条件も満たす | 語彙数未満の 8 の倍数（例 `8`、`16`） | 先頭 N 行だけで draft token を選ぶ |
| 正数でも高速 head の条件を満たさない | `7`、語彙数以上、`16` 以外の値を返すモデル形状 | 全語彙の head 計算へ fallback する。値の clamp やエラー終了はない |

`atoi` は文字列全体の厳密な検証をしない。先頭の空白や符号の後の数値部分を読み、数値の後ろに文字があっても数値部分を使う（例: `16junk` は 16）。数値として始まらない文字列は 0 となる（例: `true`）。この変数について大文字小文字を比較する処理はない。変換後の上限 clamp はなく、語彙数以上は後段の head 条件で全語彙計算に戻る（`engine/src/qwen35/q36_engine.cu:5557-5558,3062-3064`）。

## 有効になる条件

- Qwen3.6-35B-A3B（GGUF family `Qwen35Moe`）として `strata::qwen35::run` に入ること。別 family のモデルではこの読み取り経路を通らない（`engine/src/program/generate.cpp:3804-3818`）。
- モデルに MTP 層があり、`--mtp N` で N が正であること。読み込んだモデルに MTP がなければ `E.mtp_d` は 0 になる（`engine/src/qwen35/q36_engine.cu:5342,5373-5378,5456,5555-5558`）。
- 通常の token 生成では forced token と full logits dump を使わず、MTP speculative step に進むこと（`engine/src/qwen35/q36_engine.cu:5614-5623`）。serve 経路では MTP を有効にし、stop 要求中でなく、context に余裕がある request が speculative step を実行すること（`engine/src/qwen35/q36_engine.cu:5238-5240`）。
- N を限定した高速 head が使われるには、`STRATA_Q36_OLD_KERNELS` が未設定で、`draft_n` が 0 より大きく語彙数未満、8 の倍数、出力 head が Q8_0、入力幅が埋め込み幅で 2048 であること。いずれかを満たさなければ全語彙で head を計算する。`STRATA_Q36_OLD_KERNELS` は値の内容ではなく設定有無で高速 kernel を無効にする（`engine/src/qwen35/q36_engine.cu:2406,3062-3077`）。

## 実行時の詳細

CLI 引数は `run` の引数走査中に処理される。モデルを読み込み、engine 初期化後に `draft_vocab < 0` のときだけ環境変数を調べ、結果を `E.draft_n` に設定する。この設定処理は run 中に一度だけ行われ、その後の環境変更は反映されない（条件確認と変換で `getenv` をそれぞれ呼ぶ）。CLI の非負値は環境変数を上書きし、CLI の負値では環境変数があればその値が使われる（`engine/src/qwen35/q36_engine.cu:5345-5380,5458-5466,5555-5559`）。

MTP の forward が draft を求めるとき `head_draft` がこの行数を使う。限定 head が選んだ候補 token は、通常モデルの verify window に通され、一致した連続 prefix だけが採用される。候補外の token は draft として拒否されるが、コード上の説明では答えは `draft_n` にかかわらず通常の greedy answer である（`engine/src/qwen35/q36_engine.cu:3054-3077,3093-3094,3998-4019`）。

## ログと測定値

この変数の値、限定 head の採用、fallback を示す専用ログはない。値が条件を満たさず全語彙 head に戻っても警告やエラーにはならない（`engine/src/qwen35/q36_engine.cu:3062-3077`）。値による終了・失敗経路は実装されていない。MTP step の通常の受理数は、非 serve の MTP 生成では `strata-q36: ... MTP ... accepted`、serve では request ごとの `drafts accepted ...` として stderr に出るが、どちらもこの変数専用の診断ではない（`engine/src/qwen35/q36_engine.cu:5269-5273,5633-5636`）。この変数の効果を定量化する資料・測定値は確認できなかった。

## 根拠

- 環境変数の読み取り、CLI 優先、0 への下限処理: `engine/src/qwen35/q36_engine.cu:5345,5380,5557-5558`
- 限定 head と全語彙 fallback の条件: `engine/src/qwen35/q36_engine.cu:3054-3077`
- MTP draft head の呼び出しと verify / 採用: `engine/src/qwen35/q36_engine.cu:3080-3094,3953-4019`
- family による engine dispatch: `engine/src/program/generate.cpp:3804-3818`
