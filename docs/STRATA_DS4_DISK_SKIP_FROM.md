# `STRATA_DS4_DISK_SKIP_FROM`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数の意味は対象外。

## 役割

DeepSeek-V4.1 専用実行ファイル `strata-dsv41` の CPU lane が、ルート重みの小さい expert を読み飛ばす処理について、対象にする層の開始番号を指定します。層番号 `li` がこの値以上のときだけ、他の条件を満たす expert が読み飛ばし判定の対象になります。実装コメント上の対象経路は、小さい window（decode と draft の検証）で、prompt path は含みません。

この変数だけでは読み飛ばしは有効になりません。別変数 `STRATA_DS4_DISK_SKIP_W` が 0 より大きいことが必要です。読み飛ばされた expert の重みは戻されず、出力が変わり得る実験機能です。

## 値と判定

値は `std::atoi()` で整数に変換し、`std::max(0, ...)` で 0 未満を 0 にします。文字列全体の妥当性検査はありません。

| 値 | `disk_skip_from` | 結果 |
|---|---:|---|
| 未設定 | 0 | 層 0 から判定対象になり得る |
| 空文字、数値で始まらない文字列 | 0 | `atoi` の結果が 0 |
| `3`、`3tail` | 3 | 層 3 以降が対象になり得る |
| `-2` | 0 | 負値を 0 に clamp |
| `99999` など層数以上 | 指定値 | 有効な層番号がこの値以上にならず、対象層なし |

この値は `Model::Impl` のメンバー初期化時に読み取られます。`Model` の生成ごとに値が設定され、そのモデルの実行中に環境変数を変更しても読み直しません（`Model::Model()` が `new Impl` を行う）。

## 有効になる条件

読み飛ばし判定に入るには、少なくとも次の条件を満たす必要があります。併用する `STRATA_DS4_DISK_SKIP_W` は同じ `Model::Impl` 初期化時に `std::atof()` で float に変換され、未設定なら 0、設定時も負値は 0 に clamp されます。したがって未設定、空文字、数値として 0 以下、または `atof` が 0 を返す文字列では読み飛ばし処理に入りません。

- `STRATA_DS4_DISK_SKIP_W` の変換値が 0 より大きい。
- 対象 layer が MTP layer ではなく、`li >= disk_skip_from` かつ `li < g.nl`。
- expert がその token の CPU lane 側にあり、通常読み込み用の expert pick に入る。
- expert の route weight が、その token の有効な expert weight 合計に `STRATA_DS4_DISK_SKIP_W` を掛けた値より小さい。
- expert のデータが `in_ram()` 判定で RAM にない。

したがって、`STRATA_DS4_DISK_SKIP_FROM` を大きくすると、その番号より前の層では読み飛ばしを適用しません。値が層数以上なら処理は実質無効です。VRAM 側の expert、MTP layer、RAM 上にある expert はこの判定では読み飛ばしません。`--ssd-cache` のゼロコピー経路で store slot から処理される expert も、`in_ram()` 判定より前の分岐で通常の pick を抜けます。

## 実行時の詳細

各 token の CPU lane 処理で、まず有効な route expert の重みを合計します。その後、CPU lane の各 expert について、重みが `disk_skip_w * wsum` 未満で、かつ `in_ram()` が false のときに `st.skipped` を増やして読み込み用 `picks` への追加を飛ばします。比較は厳密な `<` です。`disk_skip_from` 自体は重みや route を変更せず、この判定を開始する層番号だけを制御します。

読み飛ばされた expert も、判定前に `l.cpu_hits`、expert profile、`l.heat` に加算されています。実装コメントは「重みは再正規化しない」と説明しています。つまり expert の出力を計算に加えず、その重みを他の expert に配り直しません。この機能は回答を変える可能性があります。

`in_ram()` は RAM tier slot の有無を先に見て、次に MXFP4 または file-backed expert のページ常駐を `os::in_ram()` で確認します。実装コメントによると Linux は全ページ、Windows は working set の sampled pages を確認します。この変数の説明では OS やメモリ管理 API 自身の挙動は扱いません。

読み飛ばしが発生すると、`strata-dsv41` は decode 中の定期 `STAT` 行に `skipped=<expert/token>` を付け、decode 終了時には `decode left out ... experts a token not in RAM (...% of the routed)` を stderr に出します。読み飛ばしがなければこれらの skip 表示は追加されません。

## 根拠

- `src/dsv41/ds4_model.cu:797-804,1042-1049,9052`: 設定値を保持する `Model::Impl` と `Model` 生成時の初期化。
- `src/dsv41/ds4_model.cu:1055-1063`: RAM tier とページ常駐を調べる `in_ram()`。
- `src/dsv41/ds4_model.cu:6230-6265`: 層番号・MTP・CPU lane・route weight・RAM 条件、および expert を pick に加えない処理。
- `src/dsv41/ds4_model.hpp:78`: `skipped` 統計の定義。
- `src/dsv41/ds4_main.cpp:847-874,1435-1460`: `STAT` と decode 終了時の表示。
- `CMakeLists.txt:797-811`: `STRATA_BUILD_DSV41` が既定 OFF で、専用 `strata-dsv41` target を作る条件。
- `docs/DETAILS.md`: `STRATA_DS4_DISK_SKIP_FROM` の説明やこの設定に結びつく性能・正確性の測定値は見つかりませんでした。性能効果や品質影響の大きさは、このコード調査からは確認できません。
