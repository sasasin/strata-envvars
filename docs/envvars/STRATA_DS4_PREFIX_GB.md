# `STRATA_DS4_PREFIX_GB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-dsv41` の serve モードで、複数の会話が共有するプロンプト開始部分の状態を RAM に別途保持する総バイト上限（GiB 単位）です。共有開始状態は、後続のリクエストが同じ token prefix を持つときに再利用されます。この変数は保持数の上限ではなく、保持数は `STRATA_DS4_PREFIX_KEEP` が決めます。

## 値と判定

| 環境変数の状態・値 | `prefix_budget` への反映 |
|---|---|
| 未設定 | 既定値 `2` GiB（`2 * 1073741824` bytes） |
| 数値文字列 | `atof` の戻り値に `1073741824` を掛け、整数 byte 数へ変換 |
| 空文字・数値として読めない文字列 | `atof` が `0` を返すため 0 bytes |
| 負数 | `max(0.0, ...)` により 0 bytes |
| `0` | 0 bytes。正のサイズの状態は保持されない |

文字列全体の検証やエラー報告はありません。`atof` のため数値の前の空白は許容され、数値の後ろに文字があっても数値部分が変換されます（例: `1.5GiB` は 1.5 として扱われます）。小数も受け付け、計算後の byte 数は整数化で小数部分が切り捨てられます。範囲外の巨大値に対する明示的な上限や検証はありません。

## 有効になる条件

- この処理は `strata-dsv41` の serve 経路にあります。CMake では `STRATA_BUILD_DSV41` が ON で、かつ `STRATA_HIP_GFX906` でない場合に同実行ファイルを定義します。
- モデルの restore point が有効である必要があります。`STRATA_DS4_RESTORE_POINTS`（未設定時 4。設定時は `atoi` を 0 から `kMarksMax` に clamp）が 0 の場合、`prefix_max` も 0 になり、共有開始状態の保存は行われません。別名 `DS4_RESTORE_POINTS` は主変数が未設定の場合に使われます。
- 共有開始位置がリクエストの `shared=N` または `pin=N`（`pin` は 256 以上）などから restore point として計画され、読み取りがその位置に到達する必要があります。`marks` や `tail` だけの非共有点では対象になりません。
- 共有開始が `STRATA_DS4_PREFIX_MIN`（既定 1024 tokens、最小 1）未満なら保存しません。画像を含む共有開始も保存しません。
- `STRATA_DS4_PREFIX_KEEP`（既定 2、負数は 0 に clamp）が 0 の場合も保存しません。

この値を指定する CLI 引数はありません。CLI の `--serve` が対象モードを選びます。ほかの環境変数との設定優先順位はなく、上記の restore point、最小 token 数、保持件数による条件と併せて働きます。

## 実行時の詳細

serve の初期化で `env_num` helper が `std::getenv` し、値があれば `std::atof`、未設定なら呼び出し側の既定値を返します。`prefix_budget` は serve 内の `const` 値として一度作られ、リクエストごとに再読込・再計算されません。共有開始の保存時には `m.slot_save` が返した byte 数が予算を超えると、その状態を捨てて戻ります。この個別の予算超過経路はログを出しません。保存に成功すると `stderr` に `ds4: kept a ... shared start ...` が出ます。

保持後、追加によって総 byte 数または `STRATA_DS4_PREFIX_KEEP` の件数上限を超える場合、最も古く使われた共有開始状態から削除します。後続リクエストが一致する状態を復元できた場合は `ds4: took back a ... shared start`、復元に失敗した場合は `ds4: taking a shared start back failed (...) - reading it again` を `stderr` に出し、その状態を外して prompt を読み直します。

## 根拠

- `src/dsv41/ds4_main.cpp:560-567` — helper の `getenv` / `atof`、serve 経路での初期値と byte 予算の計算。
- `src/dsv41/ds4_main.cpp:804-806` — restore point 条件、保持件数、byte 予算、最小 prefix 長。
- `src/dsv41/ds4_main.cpp:824-857` — 保存条件、state 保存、予算判定、LRU 削除、成功ログ。
- `src/dsv41/ds4_main.cpp:859-873` — 復元と失敗時のログ。
- `src/dsv41/ds4_main.cpp:1146-1183,1242-1248,1264-1268,1297-1303` — リクエストの共有 restore point と、共有開始状態を保存する条件。
- `src/dsv41/ds4_model.cu:7167-7173` — restore point 数の環境変数、既定値、clamp、別名。
- `src/dsv41/ds4_main.cpp:2574-2588` — CLI に `--serve` があり、`--parallel` は別設定であること。
- `CMakeLists.txt:931-945` — `STRATA_BUILD_DSV41` による実行ファイルのビルド条件。
