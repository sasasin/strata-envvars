# `STRATA_STAGER_RING`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

プロンプト処理で、通常の pinned arena に収まらない expert blob をホスト側で読み込み／コピーし、GPU への DMA に渡すための Stager ring の深さを指定します。各 job は `job 番号 % kRing` のホストバッファを使い、同じバッファを再利用する前に前回の DMA 完了を待ちます。そのため値は同時に先行できるコピー数の上限に関わり、リング用バッファや完了管理データの数も変えます。対象はプロンプトの expert staging 経路であり、通常の pinned expert の読み出しを直接変更する設定ではありません。

## 値と判定

| 状態 | `kRing` |
|---|---:|
| unset、通常の RAM／非 transient source | 16 |
| unset、GGUF transient source のファイル profile | `4 * threads`（通常 128。`STRATA_STAGER_THREADS` を指定した場合はそのスレッド数の4倍） |
| 設定あり | `clamp(atoi(value), 2, 256)` |

設定値は `std::atoi` で変換し、結果を 2～256 に clamp します。文字列全体の妥当性は検査しないため、数値の後ろの文字は無視されます。数値に変換できない文字列や空文字は `atoi` が 0 を返すため 2 になります。負値も 2、256 を超える値も 256 です。変換後の値を clamp するので、例えば `1tail` は 2、`20tail` は 20 になります。

`getenv()` が非 null なら値が明示設定されたものとして扱います。従って空文字も unset とは異なり、2 に設定されます。また、明示設定があればファイル profile の `4 * threads` 自動設定は適用されず、明示値の parse 結果で上書きされます。

## 有効になる条件

設定は CUDA 系実装と SYCL 実装の Stager 初期化にあります。Stager は `Prefill::init()` で初回に作られ、`m.stager` が存在する間は再初期化されません。値は `static` cache ではありませんが、すでに作られた Stager に対してプロセス実行中に環境を変更してもリング深度は変わらず、新しい Stager の初期化時に読み直されます。

明示設定はファイル source の自動 profile に優先します。CUDA 系では transient source を検出し、`STRATA_STAGER_THREADS` が未指定の場合、さらに `STRATA_STAGER_SSD` またはページキャッシュの判定でファイル profile を使うか決めます。ファイル profile でない場合は通常のスレッド数（2～4）と深さ16が使われます。SYCL では transient source ならファイル profile のスレッド数（指定がなければ32）を選び、リング深度は同様にスレッド数の4倍にします。スレッド数自体は `STRATA_STAGER_THREADS` により1～32に clamp されます。

実際にリングのバッファを使うのは、prompt staging が必要で、expert が source から一時的に読み出されるか、通常メモリ上にあるが pinned でない場合です。全 expert が pinned である場合など、Stager job を使わない経路ではリング深度によるコピー進行の変化はありません。

## 実行時の詳細

初期化時に `kRing` 個のホストバッファと対応する DMA 完了管理要素を用意します。CUDA 系では各バッファに CUDA event、SYCL では event と sequence 管理用 host memory を割り当てます。pinned host allocation に失敗したバッファは pageable な `std::vector` の領域にフォールバックします。Stager の初期化または必要な host buffer/event の準備に失敗すると、prompt 初期化は失敗し、`prefill: host buffers or events for a chunk of ... tokens` をエラーとして返します。

コピー thread は job をホストバッファへ読み込み、launch 側はその job の準備完了を待って DMA を queue します。同じ ring slot を再利用するとき、コピー thread は slot の前回 DMA が完了するまで待機します。値を大きくすると先行できる job と同時に確保する staging 用領域が増えます。ログ出力や生成値を直接切り替える環境変数ではなく、この ring 深度を介して prompt の staging／DMA 重なりに影響します。

## 文書との照合

`docs/DETAILS.md` は、GGUF を in-place で読む SSD profile の例を32 threads・128 deep ring、通常の RAM profile を既定4 threads・16 deep ring と記載しています。`docs/UNSLOTH_Q4.md` も、GGUF から読み込む場合に `STRATA_STAGER_THREADS` / `STRATA_STAGER_RING` で自動設定を override できると説明しています。現行コードでは、unset 時のファイル profile 深度が `4 * threads` であり、32 threads なら128、通常 profile なら16となるため、記載と一致します。測定値は特定の SSD/GGUF とハードウェアの説明であり、この環境変数単独の性能保証ではありません。

## 根拠

- `src/prefill/prefill.cpp:402-410,435-449` — CUDA 系 Stager の目的、既定値、値の parse/clamp、リング資源の確保。
- `src/prefill/prefill.cpp:485-505,552-563` — ring slot 再利用時の DMA 完了待ち、job 完了待ち、DMA event 記録。
- `src/prefill/prefill.cpp:1101-1133,1180` — Stager 初期化、transient/file profile、thread 数と ring 深度の関係、初期化エラー。
- `sycl/src/prefill/prefill.cpp:344-352,382-417,498-529` — SYCL 側の既定値、parse/clamp、資源確保、job 完了と再利用待ち。
- `sycl/src/prefill/prefill.cpp:999-1016,1104` — SYCL 側の Stager 作成、file profile と `STRATA_STAGER_THREADS` の扱い。
- `docs/DETAILS.md:1562`、`docs/UNSLOTH_Q4.md:174-179,228-235` — ring 深度を含むファイル／RAM profile と override の説明。
