# `STRATA_PREFILL_ALWAYS_BORROW`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`generate.cpp` の prompt prefill 用バッファの cache slot 借用計画が成立した後、prompt 用の自前バッファを置けるほど空き VRAM がある場合にも借用を維持するためのスイッチです。通常は、空き VRAM が prefill の自前バッファ所要量より 4 GiB を超えて多ければ、計画済みの借用を取り消して自前バッファを使います。この変数を認識するとその取り消し判定を飛ばします。値だけで借用計画を作ったり、`--no-prefill-borrow` を解除したりはしません。`engine/src/program/generate.cpp:23884-23890,23970-23989`。

借用が続く場合、prompt path は expert cache の末尾側の slot を借りて prefill を行い、prompt 後に貸した slot を補充して decode tier に戻します。借用した slot はその間 resident expert の保持に使えません。`engine/src/program/generate.cpp:23990-24006,24062-24101`。

## 値と判定

読み取りは `std::getenv` の戻り値について、未設定でないことと先頭 1 文字が `'1'` であることだけを確認します。文字列全体の比較や数値変換はありません。空文字は設定済みでも無効です。`engine/src/program/generate.cpp:23974-23977`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `generate.cpp` の借用処理（Metal でない経路） | `no_free_skip=false`。他の条件を満たすと空き VRAM 判定で借用が取り消されることがある | `1`, `10`, `1anything`（先頭文字が `1`） | 空文字、`0`, `true`, `false`, ` 1`, `01`（先頭文字が `1` ではない） |

大文字小文字の規則はなく、空白除去・数値妥当性・境界値の検査もしません。`1` 以外の文字列は先頭 1 文字だけで判定します。`engine/src/program/generate.cpp:23974-23977`。

## 有効になる条件

- バッチ prefill がある（`o.prefill_chunk > 0` かつ prompt が 1 token より長い）こと。`engine/src/program/generate.cpp:23884`。
- `--no-prefill-borrow` が有効でなく、host residency 情報と device residency 表があること。`--no-prefill-borrow` が指定されると借用候補を計算する外側のブロックに入りません。`engine/src/program/generate.cpp:4030,23887-23890`。
- `plan_lend` が正の slot 数を返し、後続の chunk 調整後も `k > 0` であること。借用できる slot がない、固定 chunk が収まらない等の場合はこの環境変数を読みません。`engine/src/program/generate.cpp:23890-23890,23949-23959`。
- Metal build ではこの判定の直前に `k = 0` とされるため、環境変数で借用させることはできません。`engine/src/program/generate.cpp:23966-23970`。`docs/SETTINGS.md:245` は対象 backend を NVIDIA と AMD と記載しています。
- `k > 0` のとき `STRATA_EXPERT_NIBBLE` が有効なら、環境変数の判定より前に借用を拒否して終了します。`engine/src/program/generate.cpp:23961-23964`。
- `o.kv_grow` が有効なら、空き VRAM 判定自体を実行しないため、この変数の値でその判定結果は変わりません。`o.kv_grow` は `--kv-grow` に加え、空でない `STRATA_KV_GROW` の先頭文字（`'0'` 以外なら on）で指定できます。`engine/src/program/generate.cpp:3903-3904,7647-7658,23978-23988`。

## 実行時の詳細

借用 slot 数 `k` が正になった場合に限り、関数内 static の初期化子で環境変数を読み取ります。これは初めてその経路を通った時に一度評価され、以後の prompt で環境変数を変更しても値は再読込されません。`--no-prefill-borrow`、Metal、借用候補なし等で一度もこの位置を通らなければ、その時点では読み取りも初期化もされません。`engine/src/program/generate.cpp:23884-23890,23966-23978`。

`no_free_skip` が false で `o.kv_grow` も false の場合、Strata は `Prefill::bytes_needed_owned(...)` で自前バッファの所要量を求め、`cudaMemGetInfo` が成功し、空き量 `fb` が `own_need + 4 GiB` を**超える**と `k=0` にして借用を取り消します。等しい場合は取り消しません。取り消し条件に達しないと `k` は維持され、`cudaGetLastError()` を呼びます（`cudaMemGetInfo` 失敗時も `k` は維持されます）。環境変数が有効ならこの free-VRAM 判定全体を飛ばし、計画済み `k` を維持します。`engine/src/program/generate.cpp:23974-23989`。

借用継続時は slot の境界を決めて elastic K/V を開始・確保し、residency 表から貸し出す slot を外して prompt prefill にバッファを渡します。prompt の後には貸した slot を補充します。`--kv-grow` が実際に cache から K/V slot を取る条件や cache サイズは別の判定に従い、この環境変数はそれらを変更しません。`engine/src/program/generate.cpp:23990-24006,24012-24017,24062-24101`。

## ログと測定値

この環境変数専用の有効・無効ログはありません。借用した場合は stderr に `strata generate: prompt path borrows %lld cache slots (%.2f GiB)`、借用しない場合は `strata generate: prompt path allocates its own buffers (no cache slots to borrow)` が出ます。`engine/src/program/generate.cpp:24005-24010`。

借用後の `kvg_ensure` が失敗すると呼び出し元は終了コード `1` を返します。prefill 初期化または実行の失敗も stderr にエラーを出して終了コード `1` を返します。prompt 後の境界 scrub、slot 補充、補充同期の失敗もそれぞれ stderr に理由を出して終了コード `1` になります。成功時に貸した slot があれば `strata generate: %zu lent slots refilled in %.1f ms` が出ます。`engine/src/program/generate.cpp:23995,24012-24017,24058-24060,24062-24101`。

この変数による性能測定値は、調査対象 commit の Strata 資料から確認できませんでした。

## 根拠

- 実際の環境読み取りと free-VRAM 判定: `engine/src/program/generate.cpp:23970-23989`
- 借用計画、CLI による抑止、Metal の抑止: `engine/src/program/generate.cpp:4030,23884-23970`
- 借用バッファの利用と slot の返却: `engine/src/program/generate.cpp:23990-24017,24058-24101`
- `STRATA_KV_GROW` と `--kv-grow` の選択・条件: `engine/src/program/generate.cpp:3903-3904,7647-7658`
- 候補一覧の説明との照合: `docs/SETTINGS.md:245`。この表は「on / off」とするだけで、値の実装上の判定は上記コードの先頭文字比較です。`terminal/data/settings-register.json:33569-33578` はこの engine 読み取り位置を登録した索引データで、別の読み取り箇所ではありません。`docs/DETAILS.md` にこの変数の記載はありません。
