# `STRATA_BATCH_GROUPS_AUTO`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版 `strata generate` で `--batch-groups` が未指定のとき、2 枚の Arc B-series（Battlemage）GPU にまたがる layer split で既定の 2 グループ pipeline を無効にするための opt-out です。値を有効化するスイッチではなく、既定で有効な特殊ケースを `atoi(value) == 0` で止めます。CUDA/HIP 側にはこの名前を読む実装がありません。

## 値と判定

SYCL の `generate.cpp` は `std::getenv()` の結果を `std::atoi()` に渡し、変換値が 0 なら `off` とします。文字列全体の妥当性や末尾は検査しません。

| 値 | `off` | 対象条件を満たすときの結果 |
|---|---:|---|
| 未設定 | false | 既定の 2 グループを選ぶ |
| 空文字 | true（`atoi("") == 0`） | 既定の 2 グループを選ばず、1 グループ |
| `0`、`0abc`、非数値文字列 | true | 既定の 2 グループを選ばず、1 グループ |
| `1`、`2`、`-1`、`1abc` | false（変換値が非 0） | 既定の 2 グループを選ぶ |

先頭の空白と符号は `atoi` の変換規則に従います。たとえば ` 0x` は 0、` 2tail` は 2 として扱われます。変換できる数字がない場合も 0 です。設定値の取得ポインター `ga` は関数内の `static` 変数に一度だけ保存され、以降この分岐で環境を再取得しません。

## 有効になる条件

この環境変数が 2 グループ既定を抑止するのは、すべて次を満たす場合です。

- SYCL の `generate.cpp` 実行経路である。
- `--batch` が有効で 0 より大きい。batch は `--serve` がない場合や 2 スロット未満の場合は先に無効化される。
- `--batch-groups` の値が 0 以下（未指定は 0、`auto` は -1）。正の数を指定した場合はこの環境変数の分岐に入らない。
- layer split の stage がある。
- GPU 0 と唯一の stage GPU の両方が Battlemage で、stage 数が 1。
- batch 数が 8 以上かつ偶数。

`--batch-groups auto` を明示した場合は、環境変数が 0 でも明示的な auto として一般の divisor 選択に進みます。したがって、2 枚の B-series と偶数 batch では 2 グループが選ばれ得ます。`--batch-groups 1` は正の値なので環境変数を読まず、1 グループを指定します。正の別のグループ数も同様に CLI 値が使われます。

この環境変数を読む箇所は SYCL 実装内だけです。CUDA 版 `src/program/generate.cpp` は `--batch-groups` を独自に処理し、対象名を参照しません。その他の SYCL backend や GPU 世代での既定値をこの環境変数が変更することもありません。

## 実行時の詳細

未指定時、上記の B-series 条件を満たし `STRATA_BATCH_GROUPS_AUTO` が未設定または `atoi` で非 0 なら、`o.batch_groups` を 2 にして stderr に `--batch-groups 2 by default: ...` を出します。値が空または 0 相当ならこの特例を通らず、未指定なら初期値の 1 グループのままです。環境変数を理由にした警告やエラーは出しません。明示的な `auto` で一般選択に進んだ場合は `--batch-groups auto: ...` の起動ログが別途あります。

グループ数が 1 より大きい場合、batch をグループ数で割ったスロット群を各 layer-split stage に流し、ある stage が一群を処理する間に次の stage が別群を処理する pipeline 経路が使われます。実際の pipeline 条件は `o.batch > 0`、グループ数 > 1、stage 数 > 1 です。グループ数が batch を割り切らない、または layer split がない場合は警告を出して 1 グループに戻します。slot session の確保後に有効 batch 数がグループ数で割れなくなった場合も 1 グループに戻します。2 slot session を確保できない場合は batch 自体を無効化します。

## 根拠

- `sycl/src/program/generate.cpp:630-634` — SYCL の `batch_groups` 初期値と、未指定時の B-series 既定に関する実装コメント。
- `sycl/src/program/generate.cpp:1935-1938` — `--batch-groups auto` は -1、その他は `atoi` で処理。
- `sycl/src/program/generate.cpp:4171-4183` — batch の serve / 最小 slot 条件、上限処理。
- `sycl/src/program/generate.cpp:4184-4203` — 環境読み取り、`atoi(...) == 0` 判定、2 枚の Battlemage と batch 条件、既定グループ決定および起動ログ。
- `sycl/src/program/generate.cpp:4205-4208,4263-4275` — 分割条件の警告、確保可能 slot 数に応じた fallback。
- `sycl/src/program/generate.cpp:9473-9485,9550-9574` — pipeline 有効条件、グループ化した slot の stage 間実行。
- `src/program/generate.cpp:789-791,3199-3203,6028-6045` — CUDA 系の別実装には対象名の読み取りがなく、batch groups は別の resolver に渡される。
