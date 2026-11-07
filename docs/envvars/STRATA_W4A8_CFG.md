# `STRATA_W4A8_CFG`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の IQ4 W4A8 prompt kernel が使う launch configuration を 4 種から選びます。この変数は kernel 自体の有効化スイッチではありません。IQ4 W4A8 kernel の使用には別の `STRATA_IQ4_W4A8` が `1` または `2` である必要があり、その値が無効または未設定なら `Context::run` は通常の MMQ 経路を続け、`STRATA_W4A8_CFG` は kernel 選択に使われません（`src/prefill/moe_mmq.cu:473-486`; `src/prefill/moe_iq4_w4a8.cu:440-449`）。

設定値 0〜3 は、いずれも 2-stage の同じ IQ4 W4A8 kernel で、1 CTA あたりの token tile 幅だけが異なります。値 0 が既定の configuration です（`src/prefill/moe_iq4_w4a8.cu:376-381,483-488`）。

## 値と判定

`cfg_index()` は `std::getenv()` で値を読み、未設定なら `0`、設定されていれば `std::atoi()` の結果を使います。変換結果が 0〜3 の範囲外なら `0` に戻します。文字列全体の厳密な数値 parse ではなく、`atoi` が認識する先頭の整数を判定します。

| 入力例 | `atoi` の結果 | 選択される設定 |
|---|---:|---|
| 未設定、空文字、`abc` | 0 | Cfg0 |
| `0`, `+0`, `00` | 0 | Cfg0 |
| `1`, `2`, `3` | 1, 2, 3 | Cfg1, Cfg2, Cfg3 |
| `  +2tail` | 2 | Cfg2 |
| `-1`, `4`, `99` | -1, 4, 99 | Cfg0（範囲外 fallback） |

数値の後ろに非数値文字が続いても、先頭の整数部分で決まります。空白や符号も `atoi` の変換規則に従います。整数として変換できない文字列と空文字は 0 になります。整数範囲を超える入力の `atoi` 結果は C/C++ の仕様上保証されず、Strata は別途検査していません（`src/prefill/moe_iq4_w4a8.cu:383-389`）。

| index | token tile 幅 `BN` | その他の template parameter |
|---:|---:|---|
| 0 | 128 | 2 stages, `MINB=1`, `EPI=1`, `WROW=72`, pipelined loop (`LOOP=1`) |
| 1 | 104 | 同上 |
| 2 | 112 | 同上 |
| 3 | 96 | 同上 |

## 有効になる条件

- `GGML_USE_HIP` ではなく CUDA 実装がビルドされていること。HIP 側の同ファイルは `iq4_w4a8_mode()` を 0 にする stub で、環境変数を読みません（`src/prefill/moe_iq4_w4a8.cu:22-29`）。Build system は CUDA 有効時にこのソースを `strata_mmq` に含めます（`CMakeLists.txt:2354-2372`）。
- `STRATA_IQ4_W4A8=1` なら IQ4_XS と IQ4_NL の product、`=2` なら IQ4_NL product について専用 kernel を先に試します。ほかの値は mode 0 として扱われ、この kernel は試されません（`src/prefill/moe_iq4_w4a8.cu:440-451`; `src/prefill/moe_mmq.cu:473-485`）。
- 専用 kernel を試しても、対象型、寸法、scale、GPU architecture、MMQ の K split 条件、pointer/data alignment の検査を通らない product は MMQ に戻ります。具体的には型は IQ4_XS / IQ4_NL、`n` は 1〜`kGatherGroupMax`、`max_rows > 0`、`w_rows` は 128 の倍数、`w_cols` は IQ4_XS なら 256 の倍数、IQ4_NL なら 128 の倍数、`y_scale == nullptr`、device compute capability は 8.0〜8.8 または 12.0、MMQ が K split しないこと、weight pointer は 8-byte、activation pointer は 16-byte alignment である必要があります（`src/prefill/moe_iq4_w4a8.cu:435-437,464-481`）。
- `STRATA_W4A8_CFG` 自体に OS・CLI・server mode・model 名ごとの条件分岐はありません。上記の CUDA prompt product 経路に到達し、専用 kernel が採用されたときに launch configuration を決めます。

## 実行時の詳細

`cfg_index()` の値は関数内の `static const int` に保存されます。最初の評価後にプロセス内の環境値を変更しても再読込しません。最初の読み取りは `STRATA_IQ4_W4A8` が `1` / `2` の初期化時に config 番号を stderr に表示する `iq4_w4a8_mode()` 経由、または対応 product の `run_iq4_w4a8()` が `switch` に到達したときです。後者の場合も最初に読んだ値が cache されます（`src/prefill/moe_iq4_w4a8.cu:383-390,440-449,483-488`）。

選択 index に応じて `launch<CfgN>` が CUDA kernel specialization を起動します。差分は `BN` で、grid の token-tile 数、dynamic shared memory の大きさ、各 CTA が扱う token tile の幅に反映されます（`src/prefill/moe_iq4_w4a8.cu:54-61,420-430,483-488`）。

有効化変数が `1` / `2` の場合、stderr の起動ログには `config N` が表示されます。終了時には kernel の実行数と、shape / NVFP4 scales / architecture / MMQ K split / alignment / type の理由別 decline 数が stderr に出ます。decline は caller に `false` を返して MMQ に続行させます。採用した kernel の後は caller が `cudaGetLastError` を `iq4 w4a8` のラベルで検査します（`src/prefill/moe_iq4_w4a8.cu:440-460,464-490`; `src/prefill/moe_mmq.cu:479-486`）。

`docs/DETAILS.md` は `STRATA_IQ4_W4A8` の対象 GPU・型・MMQ fallback を説明していますが、`STRATA_W4A8_CFG` ごとの性能差や推奨値は記載していません。この調査でも build・GPU 実行・性能測定は行っていないため、configuration ごとの速度優劣は判断できません（`docs/DETAILS.md:1082`）。

## 根拠

- 読み取り、範囲 clamp、configuration 定義、selection、cache: `src/prefill/moe_iq4_w4a8.cu:376-390,483-488`。
- CUDA/HIP 差、architecture 条件、product 検査と fallback: `src/prefill/moe_iq4_w4a8.cu:22-29,435-437,464-490`。
- 専用 kernel の有効化と caller の error check: `src/prefill/moe_iq4_w4a8.cu:440-460`; `src/prefill/moe_mmq.cu:473-486`。
- CUDA build でのソース登録: `CMakeLists.txt:2354-2372`。
- 関連する `STRATA_IQ4_W4A8` の概要: `docs/DETAILS.md:1082`。
