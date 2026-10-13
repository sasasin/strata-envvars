# `STRATA_BATCH_MTP_SERIAL`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

レイヤー分割と `--batch` を使う際、環境変数が有効で、`--batch-mtp` も有効なら、明示的な `--batch-groups` がないときのグループ自動選択を1グループにします。これによりスロット群を GPU ステージ間でパイプライン処理せず、各スロットの MTP 提案を含む直列ウィンドウで実行できるようにします。`--batch-mtp` 自体を有効にする変数ではありません。

## 値と判定

CUDA側 `src/program/generate.cpp` は、処理時に `getenv` した文字列の先頭文字を判定します。

| 環境変数の状態 | `mtp_serial` |
| --- | --- |
| 未設定 | false |
| 空文字 | false |
| 先頭文字が `0` | false（後続文字は判定しない） |
| それ以外の文字列 | true |

したがって `1` に限らず、例えば `true` や `2` も有効です。数値変換や文字列全体の比較は行いません。値は `static` に保存されず、グループ判定用 lambda が呼ばれるたびに読み直されます。

## 有効になる条件

- `--batch-mtp`（または `STRATA_BATCH_MTP`）が有効であること。`--batch-mtp` は `--batch` が2以上、`--mtp` が指定済み、`--spec T` が `T >= 2`、サーバーモード (`--serve`) であることを要します。レイヤー分割時は各ステージが別々の GPU にあり、helper expert cache や `--remote-expert-opt` を使わないこともゲート条件です。条件を満たさなければ `--batch-mtp` は警告付きで無効化されます。
- レイヤー分割があり、2以上の `--batch` に対して `--batch-groups` を指定していないこと。この場合に限って、通常の暗黙の `auto` グループ数より本変数が優先されます。レイヤー分割なしでは暗黙の自動グループ化は起こらず、この変数による変更もありません。
- `--batch-groups 1`, `--batch-groups N`, または明示的な `--batch-groups auto` がある場合は、その指定が優先され、本変数では直列化しません。明示的な `auto` が複数グループを選び、MTPと両立できない場合は、後段のゲートが `--batch-mtp` を無効にします。
- `--batch-mtp` が無効なら本変数はグループ数に作用しません。暗黙の自動グループ数を直列化する別条件として `--adapt-async 1` がありますが、MTPと両方が有効で本変数も有効なら MTP側の理由が選ばれます。

## 実行時の詳細

CUDAの `generate` は、バッチ用セッションを作る前に `batch_groups_for` を用いて自動グループ数を解決します。暗黙の自動選択では、GPUステージ数とバッチスロット数を上限に、スロット数を割り切れる最大のグループ数を選びます。`--batch-mtp` と本変数がともに有効なら `resolve` がその自動結果を1に置き換えます。例えば自動なら2グループになる構成で、本変数が有効なら1グループとなり、MTP提案付き直列ウィンドウを維持します。

暗黙のパイプラインが選ばれた場合は `--batch-mtp` を無効にし、`strata generate: WARNING: --batch-mtp is off: ...` を stderr に出します。自動選択の結果、直列化された場合は stderr に `strata generate: --batch-groups auto: 1 group ... - --batch-mtp does not run in pipelined groups; --batch-groups N would pipeline them and turn it off` の形式で理由と、パイプライン時のグループ数を表示します。明示的な `--batch-groups auto` が複数グループを選ぶ場合はパイプライン側となり、MTPが無効になります。

直接の読み取りは `src/program/generate.cpp` の CUDA側実装1か所です。`sycl/src/program/generate.cpp` にこの環境変数の読み取りや同等の自動グループ解決処理はありません。そのため、この調査で確認した変数の効果はCUDA側の `generate` 経路に限られます。

## 文書との照合

`docs/BATCHING.md` は、レイヤー分割で `--batch-mtp` と `--batch-groups` が未指定の場合、既定のパイプラインがMTPを無効にすること、`STRATA_BATCH_MTP_SERIAL=1` で直列ウィンドウを保てることを説明しています。これは現行ソースの分岐と一致します。資料には RTX 3080 2枚、Xeon E5-2696 v4、UD-Q4_K_XL、`--parallel 2 --spec 4` などの条件を記した測定表がありますが、その値は資料内の測定結果としてのみ扱い、本調査では再計測していません。

## 根拠

- `src/program/generate.cpp:4350-4367` — 暗黙の自動選択の説明、入力の組み立て、環境変数の値判定、`STRATA_BATCH_MTP` との組み合わせ。
- `src/program/generate.cpp:4368-4389` — MTP利用条件と、パイプライン選択時の無効化・警告。
- `src/program/generate.cpp:4404-4423` — 解決結果をオプションに適用し、自動選択を stderr に通知。
- `include/strata/program/batch_groups.hpp:40-64` — 自動グループ数と、暗黙の既定値におけるMTP直列化の優先規則。
- `src/program/generate.cpp:9656-9664` — パイプライン実行経路とMTPドラフトが動かない場合の警告。
- `sycl/src/program/generate.cpp:3896-3905` — SYCL側は `STRATA_BATCH_MTP` を読み取るが `STRATA_BATCH_MTP_SERIAL` は参照しない。
- `docs/BATCHING.md:22-39, 41-64, 85-90` — 利用条件、測定記録、環境変数と明示的な `--batch-groups` の説明。
