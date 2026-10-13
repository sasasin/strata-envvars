# `STRATA_PREFILL_CPU_SHARE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

プロンプトの prefill で、GPU の VRAM cache にない routed expert の一部を、通常 decode を担当する CPU expert pool に計算させる。CPU pool はプロンプト処理中に遊休しており、CPU は RAM から expert を読み、GPU は残りの expert を PCIe 経由で読みながら処理する。CPU の行は GPU 側の expert 行と同じ combine 入力に加えられるが、CPU 固有の activation format で計算するため、結果が GPU のみの場合と bit-identical になるとは限らない。

対象は CUDA の prefill 実装である。未設定時の既定 ON は、単一 GPU・CPU pool あり・batch slot なし・GPU cache に未常駐 expert があり、かつホストメモリ判定を通る経路に限られる。layer split では各 stage に CPU pool を設定でき、同じ pool を使う stage は一つずつ share を取得する。batch slots がある場合と HIP build では既定 ON にならない。明示設定は既定条件とは別に扱われる。

## 値と判定

| 環境変数 | 解釈 |
|---|---|
| 未設定 | 通常は share 比率 `0`。既定 ON の経路で `arm_cpu_share(..., true)` が呼ばれた場合だけ、測定値を使う `auto`（内部値 `-1`）として扱う。 |
| 正確に `auto` | 大文字小文字を区別する完全一致で、測定型の自動割合。 |
| その他の文字列 | `std::atof` で double に変換し、`[0.0, 1.0]` に clamp する。たとえば `0.4` は固定割合、`2` は `1.0`、`-1` は `0.0`。空文字や数値に変換できない文字列は `atof` の結果 `0` となる。数値の後ろに変換可能な接頭部があれば、その数値接頭部が使われる。 |

`auto` の比較は `strcmp` によるため `AUTO` などは `auto` と同じ扱いにならず、`atof` 経由で `0` になる。値を読む accessor は関数内 `static` にキャッシュされるので、プロセス起動後に環境を変更しても再読込しない。値の parse 自体に明示的なエラー表示はない。

固定割合は、その layer で GPU cache にない routed expert 数の割合を CPU に割り当てる目安で、実際には候補 expert をその routed token 数が少ない順に取り、CPU が安定した blob を得られない場合は GPU 側に残す。`auto` は同じ候補選択に使う割合を実測する。`STRATA_PREFILL_CPU_SHARE=0` は CPU share を無効にする。

## 有効になる条件

- share を使うには CPU pool が設定され、chunk が streaming-only の大きさでなく、GPU cache 外の routed expert を source から扱える必要がある。share の処理対象は routing 後に staging される chunk である。
- share が ON なら chunk の staging 上限は既定で 3072 tokens（`STRATA_PREFILL_CPU_SHARE_MAX`）。未設定の既定 ON 経路では、測定範囲を 1024 tokens に制限する。`STRATA_PREFILL_STREAM_MIN` が 0 以上で設定されると streaming 判定の閾値がそちらで上書きされるため、share の chunk 範囲にも影響する。
- 未設定時の既定 ON は、CUDA 系の compile guard 内だけで設定される。単一 GPU、pool あり、batch slot なし、未常駐 expert があることに加え、RAM、Windows commit、file-backed expert pages の余裕を満たす必要がある。メモリ判定は share 自身の buffer 量に Linux 等の RAM 余裕 3 GiB、Windows commit 余裕 4 GiB を加えて確認する。
- 明示値（`0` を除く）はメモリ判定で既定 ON を見送る場合でも設定として保持され、メモリ不足の警告を出す。明示値 `0` は無効化なので、この警告対象ではない。
- `auto` のとき、最初の適格 layer は比較用に share 有無を交互に実行し、3 比較が揃うまでは探索を続ける。その後は通常、29 layer ごとに反対側を測定し、share ありの方が速いと測定された場合に share する。固定割合ではこの性能判定を行わない。
- layer split の複数 stage は pool を一つずつ取得し、同じ時刻に複数 stage が CPU share を実行しない。通常の multi-GPU 経路は `generate` 側で pool を割り当てない。

## 実行時の詳細

`generate` / `serve` は prefill setup 時に既定 share の可否を判定し、`Prefill::arm_cpu_share` に適用可能性と既定可否を渡す。既定 ON になった場合、stderr に `prefill: the CPU share is ON by default for prompt chunks below 1024 tokens ...` を出す。適格な expert が GPU cache に全てあるときは、serve が既定 share を arm しない理由を stderr に出す。ホストメモリ不足の場合は既定を arm せず理由を表示し、明示値を指定している場合（`0` 以外）は警告を出す。

`auto` は CPU expert あたりの CPU 時間と GPU の streamed expert あたりの時間を running mean として測り、両者の時間が揃う割合を算出する。分担割合は計算時に `[0.05, 0.9]` へ clamp される。別途、share 有無の layer wall time を比較して遅い場合の share を抑える。固定数値の場合はその数値の割合を使い、auto の適否測定をしない。

CPU activation buffer または rows buffer の pinned allocation に失敗すると、その run では `m.cpu_dead` を立てて share を止め、GPU が全 expert を処理する旨を stderr に表示する。これはリクエストを allocation failure で失敗させないための fallback である。CPU の expert rows は `Dm` の末尾にコピーされ、通常の combine 処理に渡される。統計には CPU share expert 数と割合が記録される。

環境値の parse と既定状態はプロセス内 static/global 状態であり、リクエストごとに環境を読み直す設計ではない。一方、`auto` の性能測定状態は prefill 実行中に layer ごとに更新される。

## 文書・測定値との照合

`docs/DETAILS.md` の「Short prompts: the CPU shares the experts」節は、0.1.41 の CUDA 単一 GPU・batch slots なしの既定 ON と、0.1.42 のメモリ不足時の既定抑止を説明しており、現行コードの既定条件と一致する。同節には RTX 3060 / Tesla P100 / RTX 5070 での測定条件、入力長、反復回数と prompt time 変化も記載されているが、ここではその文書上の結果として扱い、独立に再測定した値とはしない。コードコメントにも 0.1.41 の既定範囲と測定条件がある。

## 根拠

- `src/prefill/prefill.cpp:154-182` — share の役割説明、`getenv`、`auto` 完全一致、`atof` と clamp、未設定時の既定切り替え。
- `src/prefill/prefill.cpp:186-193, 1918-1931` — staged chunk 閾値と既定 ON の設定、CUDA/HIP compile guard。
- `src/program/generate.cpp:6899-6926, 6978-6986, 7259-7286, 12556-12610` — メモリ verdict、既定可否、batch/pool 条件、serve の stage pool と generate の pool 設定。
- `include/strata/prefill/share_rules.hpp:15-17, 21-59` — 未常駐 expert の有無とホストメモリ判定、警告理由。
- `src/prefill/prefill.cpp:2298-2312, 3085-3109, 3116-3163, 3204-3235, 3310-3365, 3914-3929` — chunk / pool gate、auto 測定、候補選択、CPU 計算、結果の combine 入力への配置。
- `include/strata/prefill/prefill.hpp:173-187` — public API の条件説明、layer split と pool の制約。
- `docs/DETAILS.md:1564-1587` — 機能説明、既定条件、測定値と結果差の記載。
