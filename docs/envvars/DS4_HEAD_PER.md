# `DS4_HEAD_PER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek V4.1 エンジンの head 行列乗算を何行ずつ実行するかを指定します。`head_share()` が `d.head.fmt != 0` の head を処理するとき、`rows` 個の活性値を `per` 行ずつに分けて `mv()` に渡します。コメントでは主に GGUF head の列挙処理を指しています。`d.head.fmt == 0` の経路はこの環境変数を参照せず、`max(1, x3::mv_cols(d.head))` を使います（`src/dsv41/ds4_model.cu:9612-9634`）。

## 値と判定

環境変数が設定されている場合、`std::atoi()` で整数化します。文字列全体の妥当性確認や範囲制限はありません。未設定の場合だけ既定値に進みます。

| 状態 | `per` |
|---|---|
| unset、`d.head.fmt != 0`、`STRATA_METAL` ビルド | `4` |
| unset、`d.head.fmt != 0`、非 Metal ビルド、`DS4_DEFAULTS` が `026` / `0.2.6` / `v0.2.6` | `4` |
| unset、`d.head.fmt != 0`、非 Metal ビルド、その他の `DS4_DEFAULTS` | `8` |
| set、`d.head.fmt != 0` | `atoi` の結果（既定値より優先） |
| `d.head.fmt == 0` | `max(1, x3::mv_cols(d.head))`。環境変数は使わない |

空文字や数字で始まらない文字列は `atoi` により `0` になります。数字の後ろに文字がある場合は数値部分が使われます（例: `8xyz` は `8`）。先頭の空白や符号は `atoi` の規則に従います。`0` または負値を設定すると、`rows > 0` のとき `for (c += per)` が終了条件へ進まないため、処理が止まらなくなります。負値では後続の `job()` に負の行数も渡り得ます。正の範囲はコードで制限されていません。数値変換不能時の fallback もなく、結果の `0` がそのまま使われます（`src/dsv41/ds4_model.cu:9625-9634`）。

## 有効になる条件

- `strata-dsv41` の DeepSeek V4.1 実行経路で `head_share()` が呼ばれること。通常の Strata 実行全体に適用される設定ではありません。`head_share()` は forward の head 行計算、チャンク処理、drafter の head 計算から呼び出されます（`src/dsv41/ds4_model.cu:7838,8673,8681,8875,8884,9675,9836,9934`）。
- 対象 head が `d.head.fmt != 0` であること。`fmt == 0` では無視されます。
- 明示値は `DS4_DEFAULTS` による既定値、および Metal / 非 Metal の既定値より優先します。CLI 引数による上書きはこの箇所にありません。

## 実行時の詳細

`DS4_HEAD_PER` は `head_share()` が呼ばれるたびに取得され、`per` はその呼び出し中だけ使われます。値自体を static cache する実装ではありません。`getenv` が非 null なら、その値を `atoi` に渡します。未設定時は Metal ビルドなら `4`、それ以外は `head_per_default(defaults_026())` で決まり、同 helper は `DS4_DEFAULTS` が上記の完全一致トークンなら `4`、それ以外なら `8` を返します。`defaults_026()` の判定は static bool に保存されるため、初回評価後の `DS4_DEFAULTS` 変更は反映されません（`src/dsv41/ds4_model.cu:9625-9631`; `src/dsv41/ds4_experts_rule.hpp:22-28,222-223`）。

正の `per` では、行列乗算を `[0, per)`, `[per, 2*per)` のような行ブロックに分け、最後のブロックだけ `min(per, rows-c)` 行に縮めます。失敗時に `mv()` は `err` を `"exl3 mv failed"` にして false を返し、呼び出し元へ失敗を伝えます（`src/dsv41/ds4_model.cu:7639-7653,9633-9635`）。環境変数自体に対する警告や値エラーのログはありません。上位の実行経路は `err` を stderr に出し、serve 経路では `ERR` 応答も返します（`src/dsv41/ds4_main.cpp:917-924`）。

## 根拠

- 候補名のコード参照は `src/dsv41/ds4_model.cu:9625` の `getenv("DS4_HEAD_PER")` のみです。もう一つの参照（`src/dsv41/ds4_experts_rule.hpp:222`）は説明コメントで、読み取りではありません。
- 既定の列数と `DS4_DEFAULTS` のキャッシュ: `src/dsv41/ds4_experts_rule.hpp:22-28,222-223`。
- head 処理の分岐、分割、無効な値の扱い: `src/dsv41/ds4_model.cu:9612-9635`。
- `DS4_HEAD_PER` を列挙する `docs/envvars/000_envvers.md` の記載（`198` 行目）に対し、Strata 所有ソースには実際の読み取りがあります。
