# `STRATA_DS4_DSPARK_CUM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

DeepSeek V4.1 (`strata-dsv41`) の DSpark speculative decoding で、draft token の confidence の累積積に下限を設けます。各 draft の confidence が `--dspark-conf` 由来の個別下限以上であることに加え、先頭からその draft までの confidence の積がこの値以上である間だけ draft を trunk の検証に回します。累積下限を `0` にすると、この累積条件は通常の confidence が非負である範囲では draft 数を減らさず、個別の confidence 下限だけが残ります。

この環境変数を読む実装は `src/dsv41/ds4_main.cpp` にあります。DeepSeek V4.1 エンジンは `STRATA_BUILD_DSV41` が有効なときだけ `strata-dsv41` としてビルドされ、この CMake option は既定で OFF です（`CMakeLists.txt:906-920`）。

## 値と判定

環境変数は `std::getenv` の結果を `std::atof` に渡し、`float` に変換します。設定値の文字列全体の検証、範囲 clamp、無効値のエラー処理はありません。

| 環境変数 | 判定結果 |
|---|---|
| 未設定 | `0.5`（RDNA4 の gfx1200 / gfx1201）または `0`（それ以外）。ただし `DS4_DEFAULTS` が旧既定値を選ぶ場合は `0`。 |
| 空文字 | 設定済みとして扱い、`atof("")` から `0`。ハードウェア既定値より優先。 |
| 数値文字列 | 先頭の数値部分を `atof` で変換。前後の空白や符号を受け付け、数値の後ろに文字があってもその部分で変換を止める。 |
| 数値に変換できない文字列 | `atof` の結果 `0`。警告や fallback はない。 |
| 負数 | そのまま使用。累積積は通常非負なので累積条件を実質通過させる。 |
| 0 より大きい値 | そのまま使用し、累積積が値を下回った draft 以降を検証対象から外す。1 を超える値は通常の confidence 積では通過できず、draft が採用されない。 |

`nan` など比較不能な値も拒否されません。累積積との `>=` 比較が成立せず、通常は draft が 1 個も残らず plain step に進みます。極端な値や `atof` の範囲外入力を個別に処理するコードはありません。根拠: `src/dsv41/ds4_main.cpp:176-180,239-243`。

## 有効になる条件

- `strata-dsv41` をビルドして実行している必要があります。`STRATA_BUILD_DSV41` が OFF のビルドにはこの機能の実行ファイルが含まれません（`CMakeLists.txt:906-920`）。
- 累積 cut の既定値 `0.5` は、HIP ビルドでエンジンが使うすべての GPU が gfx1200 または gfx1201 の場合だけです。CUDA ビルドや Strix Halo (gfx1151)、その他の AMD GPU では既定値は `0` です。明示設定した `STRATA_DS4_DSPARK_CUM` はこの既定値を上書きします。GPU 判定は `Model::gpus_are_gfx12()` から `rdna4()` に至り、HIP build macro の下で全 device の `gcnArchName` を確認します（`src/dsv41/ds4_model.cu:932-949,10749-10750`）。
- `DS4_DEFAULTS=026`, `DS4_DEFAULTS=0.2.6`, または `DS4_DEFAULTS=v0.2.6` は、環境変数が未設定の場合の累積 cut を `0` にします。比較は文字列全体で行われ、大文字小文字や余分な文字は一致しません。明示設定された `STRATA_DS4_DSPARK_CUM` が優先されます（`src/dsv41/ds4_experts_rule.hpp:16-28,197-201`）。
- `round()` が speculative path に入り、`spec` が真、`room > 1`、`m.draft_block() > 0` のときだけ cut が draft 選別に使われます。DSpark が無効、draft block がない、出力余地が 1 以下などで plain step になる経路では、この値は選別に影響しません（`src/dsv41/ds4_main.cpp:218-243,266-272`）。
- 個別 confidence 下限 (`--dspark-conf` または serve 起動時の同等設定) が先に適用されます。累積 cut は、各 draft の confidence がその下限以上であることに加わる条件です（`src/dsv41/ds4_main.cpp:241-243,1332-1343`）。

## 実行時の詳細

`dspark_cum_default()` の最初の呼び出しで `std::getenv("STRATA_DS4_DSPARK_CUM")` の返り値ポインターを `static` に保存します。通常の CLI decode では speculative round の最初の draft 生成が成功した後、累積値が未指定 (`cum_min < 0`) の場合にこの関数を呼びます。その後の round では保存した環境値を再利用し、プロセスの環境を後から変えても `getenv` を再実行しません。`std::atof` による変換自体は同関数の呼び出しごとに行われます（`src/dsv41/ds4_main.cpp:176-180,218-243,1525-1532`）。

`strata-dsv41 --serve` の `GEN` / `GENI` リクエストでは、`dspark_cum=F` と別名 `spec_cum=F` を指定できます。値は `std::strtof` で変換されます。指定が `0` 以上ならそのリクエストの累積下限になり、環境変数より優先されます。指定値が負なら `cum_min < 0` の既定値扱いとなり、環境変数（なければ GPU と `DS4_DEFAULTS` に基づく既定値）に置き換わります。CLI に累積 cut 専用の option はなく、`--dspark-conf` は個別 confidence 下限を指定します（`src/dsv41/ds4_main.cpp:276-288,353-385,388-394,989-994,1332-1343`）。

選別では `cum` を `1.0` から始め、各 draft の confidence を順に掛けます。draft の個別下限、累積下限、`room - 1`、`--dspark-depth`、draft 数のいずれかに達したところで、それ以降を検証に送りません。1 個以上残れば `m.verify()` を呼び、0 個なら通常の `m.step()` と trunk の sampling に進みます（`src/dsv41/ds4_main.cpp:239-272`）。この環境変数専用のログ、警告、無効値エラーはありません。通常の実行では speculative decoding の統計として `dspark: ... drafts offered, ... accepted` と per-position 集計が stderr に出ます（`src/dsv41/ds4_main.cpp:1546-1553`）。

## 根拠

- `src/dsv41/ds4_main.cpp:169-180` — cumulative cut の説明、環境値の読み取りと既定値 helper 呼び出し。
- `src/dsv41/ds4_experts_rule.hpp:16-28,197-201` — `DS4_DEFAULTS` と gfx12 / 旧既定値のルール。
- `src/dsv41/ds4_main.cpp:218-272` — speculative round の条件、confidence の選別、検証または plain step。
- `src/dsv41/ds4_main.cpp:276-288,353-385,388-394,989-994` — serve request の値と alias、request ごとの優先順位。
- `src/dsv41/ds4_model.cu:932-949,10749-10750` — HIP GPU 世代判定と `Model` accessor。
- `CMakeLists.txt:906-920` — `strata-dsv41` の build option と対象ソース。

`docs/DETAILS.md` にはこの環境変数の挙動や累積 cut の測定説明は見つかりませんでした。性能値は本書では主張しません。
