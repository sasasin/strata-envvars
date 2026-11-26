# `STRATA_METAL_MTP_Q8`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal の MTP draft layer を読み込むとき、対象となる BF16 行列を Q8_0 に変換して別バッファに置くかを選ぶ。未設定時は変換する。値が文字列全体で `0` の場合だけ変換を行わず、draft 行列は GGUF 内の BF16 のまま使う。対象は Metal の MTP draft layer であり、主モデルや verifier の重みを切り替える設定ではない。実装は `Window::mtp_load()` と同ファイルの MTP 行列参照処理にある（`engine/metal/src/engine/window.cpp:2497-2521,2524-2552,2648-2653,2707-2722`）。

## 値と判定

`Window::mtp_load()` が `std::getenv` で取得し、値全体を `std::string(e) == "0"` と比較する。数値変換や trim、真偽値の解釈はしない。したがって空文字は「設定済み」でも Q8 変換を止めず、`0` との完全一致だけが無効化値になる（`engine/metal/src/engine/window.cpp:2520-2522`）。

| 条件 | unset | Q8_0 変換を行う値 | 変換を止め BF16 を使う値 |
| --- | --- | --- | --- |
| Metal の MTP layer 読み込み時 | 変換する | `1`, `true`, `false`, 空文字, `00`, `0anything`, ` 0`, `-0` など、文字列全体が `0` でない値 | `0` のみ |

値の長さ・数値としての妥当性・大文字小文字は検査しない。CLI 引数や別の環境変数との優先順位もこの判定にはなく、読み込み時点の環境値だけで決まる（同 `2520-2522`）。

## 有効になる条件

- `STRATA_GPU_METAL` を定義したビルドの Metal 経路で使われる。共通 `MtpDrafter::load()` はこのビルド条件で Metal engine の `mtp_load()` を呼ぶ（`engine/src/core/mtp.cpp:81-90,345-354`）。
- MTP drafter のロード後に Metal decode window が初期化され、保留中の MTP GGUF が読み込まれる必要がある。MTP が設定されていない場合 `mtp_load_pending()` は `true` を返して draft layer のロードを行わず、この変数も評価されない（`engine/metal/src/engine/window.cpp:3627-3635,3705-3729`）。
- Q8 変換が有効な値でも、変換対象は MTP GGUF 内で型が BF16、rank が 2 以上、shape の第 0 次元が 32 の倍数である tensor に限る。それ以外の tensor は変換対象外（同 `2524-2536`）。

## 実行時の詳細

共通 MTP loader は Metal engine にロードを依頼し、Metal 側はロード先パスを保持する。decode window の初期化時に `mtp_load_pending()` が `Window::mtp_load()` を呼ぶ。この関数は MTP GGUF を開き、Metal buffer の wrap と MTP kernel の compile の後、環境変数を一度読む（`engine/src/core/mtp.cpp:345-354`; `engine/metal/src/engine/window.cpp:2515-2522,3627-3635,3708-3729`）。読み取り結果は変数専用の static cache には保存されないが、同じ `mtp_load()` の中で一度だけ判定され、そのロードで作る `mq8t_` / `mq8_` の構成に反映される。ロード後に環境を変えても、その既存 draft layer の形式は変わらない。

変換を行う場合、対象 tensor の Q8_0 サイズを積算して Metal buffer を確保し、最大 16 本（`hardware_concurrency()` に応じて 1〜16 本）の thread で BF16 を float に dequantize してから Q8_0 に quantize する。`mq8t_` は変換 tensor の型・offset・byte 数を記録し、`TQ()` / `MB()` はその tensor に限って変換後の metadata と `mq8_` を返す。MTP の `gr_read_m()` と `mtp_encode()` 内の GEMV はこの選択を通じて Q8_0 tensor と対応 buffer を使い、対象外または変換停止時は元の MTP buffer `Wm_` を使う（`engine/metal/src/engine/window.cpp:2522-2552,625-629,2648-2653,2707-2722`）。

## ログと測定値

この変数の値や Q8 変換件数だけを報告するログはない。MTP load が成功すると、設定値にかかわらず stderr に `strata metal: MTP draft layer from ...` の行が出る（`engine/metal/src/engine/window.cpp:2639-2642`）。変換無効化時専用のログや、この変数に結び付いた測定値はソースで確認できない。

## 根拠

- `engine/src/core/mtp.cpp:81-90,345-354` — Metal build guard と共通 MTP loader からの委譲。
- `engine/metal/src/engine/window.cpp:2520-2552` — 値判定、対象 tensor 条件、buffer 確保と変換。
- `engine/metal/src/engine/window.cpp:625-629,2648-2653,2707-2722` — 変換後 tensor と buffer の選択、および MTP GEMV からの参照。
- `engine/metal/src/engine/window.cpp:3627-3635,3705-3729` — window 初期化、MTP がない経路、保留ロード。
- `engine/metal/src/engine/window.cpp:2639-2642` — MTP load 成功時の stderr ログ。
