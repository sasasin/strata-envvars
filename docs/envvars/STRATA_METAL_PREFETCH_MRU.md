# `STRATA_METAL_PREFETCH_MRU`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Metal engine の SSD expert streaming で、次 layer の予測に基づいて先読みした expert slot を LRU 順の先頭（MRU 側）へ置くか末尾（victim に選ばれやすい側）へ置くかを決めます。値は `ExpertStream::open()` 時に読み取られ、既定値は layer あたりの平均 expert サイズに応じて変わります。

## 値と判定

読み取りは共通 helper `env_int()` を通ります。変換は `std::atoi()` で、文字列全体の検証やこの変数固有の clamp はありません。

| 値 | 判定・効果 |
|---|---|
| 未設定または空文字 | 平均 expert サイズに基づく既定値を使う。 |
| 整数変換結果が `0` | 先読み expert を LRU 末尾へ置く。 |
| 整数変換結果が `0` 以外 | 先読み expert を LRU 先頭へ置く。負の値も有効側。 |
| 数字に続く文字がある値 | `atoi()` が読める先頭の数値部分で判定する。例: `1xyz` は有効側、`0xyz` は無効側。 |
| 数値に変換できない文字列 | `atoi()` の結果は `0` となり、無効側。 |

したがって `true` は有効値ではなく、`-1` は有効値です。空白や符号を含む入力も `atoi()` の変換規則に従います。

既定値を選ぶ `big` は、全48 layerについて gate/up/down expert の合計 byte 数を合計し、layer 数で割った平均が `1.5e6` byte を**超える**かで決まります。超える場合は既定 `0`、それ以外は既定 `1` です。明示設定した非空文字列はこの既定値を上書きします。

## 有効になる条件

この値を読むのは Metal engine の `ExpertStream::open()` です。window 初期化で `ExpertStream::wanted()` が true になり SSD streaming 経路が作られた場合にだけ読み取られます。モデルが resident 経路を使う場合、この環境変数による処理はありません。

先読み位置を変える効果は、decode の layer handoff で予測 router logits があり、先読み対象の layer が残っている場合に現れます。layer `l` から `l+1` への先読みは `STRATA_METAL_PREFETCH` が有効（既定の `pre_k_ > 0`）な場合に呼ばれます。`l+2` への先読みは別変数 `STRATA_METAL_PREFETCH2` が正の値で、`pred2` がある場合に呼ばれます。prompt chunk の別処理は次 layer の欠けた expert を streaming しますが、この MRU フラグの先読み配置分岐は通りません。

## 実行時の詳細

`ahead()` は予測 logits から候補 expert を選び、該当 slot が既にある場合は LRU 先頭へ移します。新しい先読みを投入する場合、`STRATA_METAL_PREFETCH_MRU` の変換結果が非ゼロならその slot を先頭へ、ゼロなら末尾へ置きます。victim 探索は LRU の末尾から空き slot を探すため、他の条件が同じなら末尾に置いた先読み slot の方が eviction 候補になりやすくなります。対象 layer で実際に必要になった先読みは urgent queue に昇格し、読み込み完了を待つ処理があります。

値は `open()` ごとに1回読み、`ExpertStream` インスタンスの `pre_mru_` に保持します。稼働中の同一インスタンスでは環境変数を変更しても反映されません。実装上、この変数による専用ログ出力やエラー終了処理はありません。

## 根拠

- `metal/src/engine/stream.cpp:27-30` — `env_int()` の unset/空文字処理と `atoi()` 変換。
- `metal/src/engine/stream.cpp:154-160` — 平均 expert サイズの閾値、関連する先読み設定、既定値と値の保存。
- `metal/src/engine/stream.cpp:245-254,256-269` — LRU の先頭/末尾操作と末尾からの victim 探索。
- `metal/src/engine/stream.cpp:575-615` — 予測先読み、新規 slot の LRU 配置、既存 slot の更新。
- `metal/src/engine/stream.cpp:617-715` — decode/prompt の分岐、必要な slot の処理、次 layer / 2 layer 先読み呼び出し。
- `metal/src/engine/stream.h:62-66,120-121` — `at_layer()` の予測入力と `STRATA_METAL_PREFETCH2`、状態メンバー。
- `metal/src/engine/window.cpp:451-458,304-306` — streaming 経路の選択と layer handoff からの呼び出し。
- `docs/MAC.md:157` — M4 で arena サイズが主な要因であり、read-ahead depth・I/O thread 数・eviction order の個別差が decode で3%未満だったとの資料記載。文書は `STRATA_METAL_PREFETCH_MRU` の値ごとの独立比較や詳細な測定条件を示していないため、この値固有の性能差としては断定しない。
