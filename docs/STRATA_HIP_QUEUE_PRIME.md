# `STRATA_HIP_QUEUE_PRIME`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部 HIP runtime / driver の内部動作は対象外。

## 役割

HIP エンジンの起動時に GPU stream を順に作成して短い処理を実行し、stream を破棄します。ソースのコメントでは、この操作により runtime が遅延作成するハードウェアキューの割り当て順を揃え、特定の AMD GPU で起きる起動ごとの prompt 速度差を抑える狙いが説明されています。Strata が行うのは、指定数の stream をこの順で作成・使用・破棄するところまでです。

## 値と判定

`std::getenv` で値を読み、空文字列かどうかを確認した後、非空値は文字列全体が正確に `"0"` かどうかで判定します。数値変換はしません。

| 値 | 動作 |
|---|---|
| `0` | 関数の冒頭で終了し、キューを priming しない。完全一致のみなので `00` はこの扱いではない。 |
| 未設定または空文字 | 自動判定へ進む。Linux では対象 GPU の判定、Windows では終了する。 |
| その他の非空文字列 | 1文字につき stream を1つ作る。文字 `h` は優先度取得に成功した場合に最高優先度 stream を要求し、それ以外の文字は通常優先度 stream を作る。例: `nn` は通常優先度2つ、`nh` は通常優先度1つと最高優先度1つ。大文字 `H` も通常優先度扱い。 |

各 stream の作成に失敗した場合はその stream を飛ばし、残りを続けます。したがって、指定文字数と実際に作られるキュー数は一致しないことがあります。

## 有効になる条件

- この関数と呼び出しは `STRATA_USE_HIP` が定義され、`STRATA_HIP_GFX906` が未定義のビルドだけに含まれます。CUDA / Metal、および gfx906 HIP ビルドではこの環境変数は参照されません。
- 値が未設定または空の場合、Windows は priming せず終了します。Linux では `STRATA_PRIMARY_DEVICE` から対象 ordinal を決め、その GPU の `gcnArchName` が `gfx1200` または `gfx1201` のときだけ自動で `nn` を使います。GPU 数取得失敗、ordinal が範囲外、GPU 情報取得失敗、その他の GPU 世代では何もせず戻ります。
- 自動判定時に限り、`GPU_MAX_HW_QUEUES` が設定され、`atoi` の結果が 1 または 2 なら自動 priming を見送り、stderr に理由を出します。`atoi` なので、例えば `2x` も値 2 としてこの分岐に入ります。非空の明示 spec はこの制限分岐を通らず、別 GPU 世代や Windows でも試行されます。
- `STRATA_PRIMARY_DEVICE` はここでは `atoi` で読み、結果が正のときだけその ordinal を使います。未設定、空、先頭が数値でない文字列、0、負値は ordinal 0 になります。`atoi` は数値部分の後ろを検査しないため、例えば `2x` は ordinal 2 です。対象 ordinal がデバイス数以上なら関数は無言で戻ります。

## 実行時の詳細

通常の `generate.cpp` 起動経路では、`prime_hw_queues()` はオプション解析の前に、モデル family が Qwen35 の専用経路へ分岐しなかった後で呼ばれます。`--gpu` による可視 GPU 環境の設定はその前に行われます。priming 用の環境判定はこの起動時の呼び出しで行われ、リクエスト単位の再読込はありません。

priming を続ける場合、関数はまず対象 device を選択し（ordinal 0 なら `cudaSetDevice` を呼ばない）、256 byte のバッファを確保します。spec の各文字について stream を作成し、各 stream 上で `cudaMemsetAsync` と同期を行ってから、作成済み stream を破棄し、バッファを解放します。`hipDeviceGetStreamPriorityRange` に失敗した場合は `h` も通常優先度 stream の作成へフォールバックします。

デバイス数取得、device 選択、バッファ確保の失敗時はエラーをクリアして無言で戻ります。個別 stream の作成失敗も飛ばされます。処理を最後まで通った場合は、作成数が 0 でも `strata generate: opened %zu GPU queues in a fixed order (STRATA_HIP_QUEUE_PRIME=0 turns it off)` を stderr に出します。自動判定が `GPU_MAX_HW_QUEUES` により見送られた場合の文言は `strata generate: GPU queues not primed: GPU_MAX_HW_QUEUES=%s leaves none for the draft stream (STRATA_HIP_QUEUE_PRIME=nn primes them anyway)` です。

## 文書との照合

`docs/AMD_HIP.md` と 0.2.1 リリースノートは gfx1200/gfx1201 の Linux を既定対象とし、`STRATA_HIP_QUEUE_PRIME=0` で無効化できることを説明しています。現行コードでは、空文字も未設定と同じ自動判定になります。また、0.2.2 リリースノートは `GPU_MAX_HW_QUEUES` が 1 または 2 のとき自動 priming を抑止し、明示 spec はそれを上書きすると記しています。測定について、0.2.1 リリースノートと AMD_HIP.md は R9700 / RX 9000 系の記載値を含みますが、その値を他の GPU に一般化しません。0.2.2 リリースノートは gfx12 カードでの制限キュー数の変更を測定していないと明記しています。

## 根拠

- `src/program/generate.cpp:2227-2290`: ビルド条件、読み取り、値判定、GPU 世代・キュー上限判定、stream 作成とログ。
- `src/program/generate.cpp:2330-2395`: `--gpu` の環境設定と priming 関数の呼び出し位置、Qwen35 専用経路。
- `include/strata/kernels/gfx_arch.hpp:30-36`: gfx12 判定が `gfx1200` / `gfx1201` との比較であること。
- `docs/AMD_HIP.md:534-544`, `docs/release-notes-0.2.1.md:46`, `docs/release-notes-0.2.2.md:23`: 説明・測定値・制限の照合用資料。
