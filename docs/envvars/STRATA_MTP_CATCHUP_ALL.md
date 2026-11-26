# `STRATA_MTP_CATCHUP_ALL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。調査開始時の checkout は `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

MTP drafter が検証窓のうち受理された行までしか更新しない通常動作を、未受理行も含む窓全体の K/V 更新に切り替える。`MtpDrafter::draft()` は既定では `T` を `a + 1` に縮めてから round を作るが、この変数が有効ならその切り詰めを行わない。round の `record_front(T, ...)` はその `T` 行の K/V を計算して K/V cache に追加し、その後の `record_rest()` と draft 選択は受理行 `a` に対して行う。したがって変数が直接変えるのは MTP drafter 側の検証窓の K/V catch-up 範囲であり、受理行の決定や draft の最大数を変える処理ではない（`engine/src/core/mtp.cpp:1885-1891,1906-1912,1250-1292,1606-1627`; `engine/sycl/src/core/mtp.cpp:1636-1645,1658-1664,950-995,1341-1373`）。

この読み取りは CUDA/HIP 用の `engine/src/core/mtp.cpp` と SYCL 用の `engine/sycl/src/core/mtp.cpp` にある。Metal は `MtpDrafter::draft()` の Metal 専用分岐で別実装 `strata::metal_engine::mtp_draft()` に委譲して先に return するため、この変数を読む共通分岐へ到達しない（`engine/src/core/mtp.cpp:1869-1883`）。

## 値と判定

両 backend とも `std::getenv()` で取得し、関数内 `static const bool` を初期化する。値全体を parse せず、未設定ではなく、かつ先頭文字が NUL と `'0'` のどちらでもない場合に ON とする（`engine/src/core/mtp.cpp:98-105`; `engine/sycl/src/core/mtp.cpp:93-100`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP | OFF | 空でなく先頭が `0` 以外。例: `1`, `true`, `false`, `anything`, ` 0` | 空文字、先頭が `0` の文字列。例: `0`, `0anything` |
| SYCL | OFF | 空でなく先頭が `0` 以外。例: `1`, `true`, `false`, `anything`, ` 0` | 空文字、先頭が `0` の文字列。例: `0`, `0anything` |
| Metal | この変数を読み取らない | 該当なし | 該当なし |

大文字小文字、空白、数値としての妥当性、文字列の残り部分は検査しない。したがって `false` や先頭に空白のある ` 0` も ON、`0yes` は OFF になる。未設定と明示的な空文字はいずれも OFF（`engine/src/core/mtp.cpp:99-104`; `engine/sycl/src/core/mtp.cpp:94-99`）。

## 有効になる条件

- エンジンが MTP の `MtpDrafter::draft()` 経路を使うこと。起動時に `--mtp` が指定され、`--spec` が 2 以上でなければ MTP レイヤーはロードされない（`engine/src/program/generate.cpp:8243-8264`; `engine/sycl/src/program/generate.cpp:4524-4542`）。
- その生成窓が DFlash2 に処理されず、MTP draft 呼び出しまで到達すること。生成ループでは DFlash2 を使う要求なら DFlash2 の処理、そうでなければ MTP の `draft_long()`（必要に応じて `draft()`）を選ぶ（`engine/src/program/generate.cpp:23141-23144,2060-2076`; `engine/sycl/src/program/generate.cpp:12920-12921`）。
- Metal では有効にならない。Metal の draft 分岐は本変数の判定より前に専用実装を呼び出す（`engine/src/core/mtp.cpp:1869-1883`）。
- CUDA/HIP の `--batch-mtp` で `STRATA_BATCH_MTP_FUSED` による fused 経路を要求している場合、本変数が ON だと `can_draft_slots()` が fused drafting を不許可にする。生成側はその場合、slot ごとの `draft()` に fallback するため、catch-up 自体は使われる（`engine/src/core/mtp.cpp:2244-2251`; `engine/src/program/generate.cpp:17292-17298,17412-17450`）。
- 判定を上書きする CLI 引数や別環境変数はこの実装にはない。`--mtp` と `--spec` は MTP 経路に入る前提条件である。

## 実行時の詳細

`mtp_catchup_all()` の結果は関数内 `static` に保存されるため、プロセス内で最初にこの helper が呼ばれた時点で値が確定し、その後の環境変更は反映されない。通常の MTP draft は検証窓 `T` と受理行 `a` を受け取り、判定が OFF なら `T = a + 1` にしてから `capture_round(T, ...)` を選び、ON なら元の `T` で round を作る（`engine/src/core/mtp.cpp:99-105,1885-1891`; `engine/sycl/src/core/mtp.cpp:94-100,1636-1645`）。

round は `record_front(T, ...)` で各行の front と K/V を処理し、その後、受理行 `a` の中間状態を使って `record_rest()` と `mtp_select()` を実行する。窓全体 `T` と採用された行 `0..a` が異なることは、生成側が `T` 行を検証し、`0..a` の token だけを消費・出力する処理にも表れている（`engine/src/core/mtp.cpp:1250-1292,1606-1627`; `engine/sycl/src/core/mtp.cpp:950-995,1341-1373`; `engine/sycl/src/program/generate.cpp:12858-12865,12920-12921`; `engine/src/program/generate.cpp:23087-23112,23141-23144`）。

子プロセスへの転送や環境値の書き換えは、この読み取り経路にはない。環境値は各 backend 実装のプロセス内 helper で読む。

## ログと測定値

この変数専用のログ、警告、終了処理はない。MTP draft 自体が失敗した場合は、生成側が通常の失敗経路として `ERR %s` を出力して終了コード 1 を返す。例えば CUDA/HIP 側では round/step graph の起動失敗が `mtp draft: ...` / `mtp draft step: ...` を `err` に設定し、生成側がそれを出力する（`engine/src/core/mtp.cpp:1938-1945,1979-1981`; `engine/src/program/generate.cpp:23185-23187`）。この環境変数による追加の測定値はソースにない。

## 根拠

- `engine/src/core/mtp.cpp:98-105` — CUDA/HIP 用の値判定と static cache。
- `engine/sycl/src/core/mtp.cpp:93-100` — SYCL 用の同等判定と static cache。
- `engine/src/core/mtp.cpp:1865-1891`、`engine/sycl/src/core/mtp.cpp:1636-1645` — draft の引数、境界検査、既定の `T = a + 1`。
- `engine/src/core/mtp.cpp:1250-1292,1606-1627`、`engine/sycl/src/core/mtp.cpp:950-995,1341-1373` — front が `T` 行の K/V を cache に追加し、round は `a` の行から rest と draft selection を行う箇所。
- `engine/src/program/generate.cpp:8243-8264`、`engine/sycl/src/program/generate.cpp:4524-4542` — `--mtp` と `--spec` による MTP load 条件。
- `engine/src/program/generate.cpp:23141-23144,2060-2076`、`engine/sycl/src/program/generate.cpp:12920-12921` — 生成ループの MTP/DFlash2 draft 分岐と long window から draft への委譲。
- `engine/src/core/mtp.cpp:1869-1883` — Metal 専用 draft 経路。
- `engine/src/core/mtp.cpp:2244-2251`、`engine/src/program/generate.cpp:17292-17298,17412-17450` — fused batch MTP の拒否と slot ごとの fallback。
