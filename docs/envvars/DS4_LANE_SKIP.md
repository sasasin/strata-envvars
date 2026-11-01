# `DS4_LANE_SKIP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DS4 engine の service thread が、ルーティングされた CPU lane expert の計算を意図的に省略する診断用フックです。ソースコメントは「timing oracle」と説明しています。これを設定すると、GPU 側の expert 結果に CPU lane の寄与が加わらなくなるため、通常の推論結果を保つ設定ではありません。

この名前を読む Strata 所有ソースは `src/dsv41/ds4_model.cu` の 1 箇所です。候補名の完全一致検索では他の参照はありません。DS4 は独立した `strata-dsv41` 実行ファイルで、CMake の `STRATA_BUILD_DSV41` は既定 OFF です。

## 値と判定

値の内容は解析しません。`std::getenv(...) != nullptr` の判定なので、空文字を含め、環境変数が存在すれば有効です。`0`、`false`、その他どの文字列でも同じ扱いです。未設定なら無効です。数値変換、範囲制限、無効値時の fallback はありません。

判定は `serve_lane()` 内の関数ローカル `static const bool` に保存されます。service thread がこの行に初めて到達した時点の値がそのプロセス内で使われ続け、実行中の環境変更は再評価されません。対応する CLI 引数や、別の環境変数による優先・上書きはこの実装箇所にはありません。

根拠: `src/dsv41/ds4_model.cu:7609`。

## 有効になる条件

- `strata-dsv41` がビルドされ実行されている必要があります。CMake では `STRATA_BUILD_DSV41` が既定 OFF で、`STRATA_BUILD_DSV41 AND NOT STRATA_HIP_GFX906` の場合に実行ファイルを定義します。通常の `strata` 実行ファイルにこの読み取り箇所はありません。
- service thread がルーティング要求を処理する経路で判定されます。デバイス側が `wp.async` の経路に入り、CPU lane の要求が公開される必要があります。CUDA/HIP では `DS4_SYNC` が存在すると同期 decode、Metal では `DS4_ASYNC` が未設定だと同期 decode です。また通常の窓幅は `DS4_ASYNC_T`（未設定時 8）以下で非同期になります。ただし別の並列経路が `wp.async` を明示する箇所もあります。
- 要求内に CPU lane expert がある場合（`ents` が空でない場合）にだけ計算を省略します。対象外の経路や空の要求では、このフックによる計算差はありません。

根拠: `CMakeLists.txt:906-920`, `src/dsv41/ds4_model.cu:1126-1136, 7609-7613, 7787, 8610, 8779, 9568, 10301`。

## 実行時の詳細

service thread は各要求の処理開始時に `rp.cpu[t]` を 0 にします。`DS4_LANE_SKIP` が設定され、CPU lane expert が 1 件以上あれば、各 token のフラグを 0 のままにして `cpu_experts()` を呼びません。要求の応答 sequence はその後も公開されるため、この分岐自体は待ち続けたりエラーを返したりしません。

デバイス側は応答フラグを `MoeArgs::cpu_flag` に渡します。Strata の API コメントでは CPU lane の部分結果は `*cpu_flag` が真の場合に加算すると定義されています。そのためこの設定時は CPU lane の部分結果が合成されず、ルーティング済み CPU expert の寄与が欠けます。GPU にある expert の計算はこの分岐では省略しません。

この環境変数を理由とするログ、警告、エラー、終了処理は確認できません。応答 sequence が進み、処理は継続します。CPU lane を使う通常の結果と等価であるという保証はありません。

根拠: `src/dsv41/ds4_model.cu:7485-7489, 7609-7634, 10328-10363`; `include/strata/dsv41/exl3.hpp:94-107`。
