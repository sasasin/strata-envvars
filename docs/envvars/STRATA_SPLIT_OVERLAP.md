# `STRATA_SPLIT_OVERLAP`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

複数 GPU の layer split で、verify window の hand-off を直列に処理せず、先行 stage の GPU が hand-off データを書き終えて ready flag を立てる方式に切り替えます。後続 stage の graph は先行 stage の処理中に起動し、GPU 上でその flag を待ちます。これにより stage 間のホスト側 stream 同期を避けます。

この環境変数は hand-off 機能を要求するスイッチです。実際に使われるには、異なる GPU に stage が分かれ、`--pipeline-windows` が無効である必要があります。通常の非 split 実行では読み取り箇所に到達しません。

## 値と判定

`src/program/generate.cpp` は layer split の stage 数が 2 以上のとき、一度だけ `std::getenv()` で値を読み、`std::atoi(v) != 0` で判定します。文字列全体の検証はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（`atoi` が 0 を返す） |
| 先頭の数値部分が 0、または数値として読めない文字列 | 無効 |
| 0 以外の整数に変換される値（負数を含む） | 要求あり |

`atoi` のため、先頭空白や符号は変換規則に従い、数値の後ろに文字が続いても数値部分で判定されます。たとえば `1junk` と `-1` は有効、`0junk` と `true` は無効です。設定値は stage 初期化時の `static const bool` に保存され、プロセス実行中に環境を書き換えても再評価されません。

## 有効になる条件

- `--split` 等で複数 stage の layer split が構成されていること（stage 数が 2 以上）。
- stage が別々の GPU に置かれること。`--split-device 0` のように同一 GPU に置く場合は `split_same` となり、要求値が真でも overlap は無効です。
- `--pipeline-windows` が無効であること。これが有効な場合は本機能を併用せず、要求値が真なら stderr に `strata serve: STRATA_SPLIT_OVERLAP is off beside --pipeline-windows %d (that loop overlaps the stages itself)` と出します。
- 対象 stage 間で後続 verifier が PLE stage ではないこと。`Verifier::chain_overlap()` は、次 stage の device が異なり、handoff flag が接続され、かつ次 stage が PLE stage ではない場合にだけ先行 stage の graph の先行起動を行います。

バッチ window はこの hand-off の `wait_handoff` / `handoff_publish` 経路を通らず、直列順を使います。Metal verifier は `Verifier::run()` 内で Metal 実装へ分岐するため、この CUDA/HIP verifier の動作説明には含めません。HIP build では CMake が CUDA 形式の `.cu` ソースを HIP 言語として扱う経路があります。性能測定は `docs/MULTI_GPU.md` に記載された AMD 環境の結果であり、NVIDIA の性能効果は同文書で未測定とされています。

## 実行時の詳細

layer split 初期化時、要求があり、同一 GPU ではなく、`--pipeline-windows` も無効なら、各 hand-off boundary 用に mapped host/device ready flag を確保して verifier に設定します。起動ログの `strata serve: layer split: ...` 行には ` (overlapped: STRATA_SPLIT_OVERLAP=1)` が付きます。無効時はこの接尾辞が付きません。

window 実行時、先行 stage は residual、pending write、inject を hand-off buffer に書き、GPU kernel `handoff_publish` で ready flag を立てます。後続 stage は helper thread から先行 stage の処理中に prelaunch され、自分の graph 内の `wait_handoff` で flag を待ってから hand-off buffer を読みます。stage の処理後に先行 stage の stream を同期します。3 stage 以上では途中 stage 自身の hand-in も確認されます。

GPU 側 flag 待ちは `STRATA_SPLIT_WAIT_MS`（別の環境変数）で制限され、既定 30000 ms、0 は無制限です。timeout するとエラー word が立ち、window は使用されず、`verify: layer split: the hand-off into layer ... did not arrive within ... ms (STRATA_SPLIT_WAIT_MS); the window was not used. STRATA_SPLIT_OVERLAP=0 runs the serial order` のエラーになります。ホスト側の layer wait watchdog が先に異常を検知して GPU wait を解放する場合もあります。

## 文書と測定値

`docs/MULTI_GPU.md` は既定では各 stage を順番に実行し、この変数で別 GPU 間 hand-off を overlap すると説明しています。2x RX 7900 XTX（gfx1100、ROCm、Linux）、Ryzen 9 9900X、Swift 1.5 IQ3_XXS、128K context、8-bit KV、512-token greedy answer、8 run の中央値として、decode は code prompt 53→70.1 tok/s、prose prompt 45→55.9 tok/s と記載されています。同文書は NVIDIA では未測定と明記しています。これらは記載条件に限る測定値です。

## 根拠

- `src/program/generate.cpp:8404-8409` — stage 数と pipeline 判定。
- `src/program/generate.cpp:8448-8469,8470-8485,8516-8522` — 環境変数判定、条件、flag 設定、起動ログ。
- `src/core/verify.cpp:2614-2617,2645-2647,2667-2672,2723-2745` — chain overlap 条件、Metal 分岐、次 stage の prelaunch。
- `src/core/verify.cpp:1074-1083,2090-2100,2864-2880` — hand-off の読み書きと stage 間の実行順。
- `src/core/verify.cpp:450-456,2605-2611` — GPU wait timeout の設定とエラー。
- `src/kernels/cuda/verify_kernels.cu:1183-1218` — bounded wait と hand-off publish kernel。
- `CMakeLists.txt:1991-2000` — HIP gfx906 build で CUDA 形式の `.cu` を HIP として扱う設定。
- `docs/MULTI_GPU.md:218-244` — 機能説明、測定条件、測定値、NVIDIA 未測定の注記。
