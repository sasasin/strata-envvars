# `STRATA_PIN_BY_NEED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

ネイティブ expert arena を開く前に、GPU expert cache に入らないと推定した expert を expert profile の順位順にホストメモリ登録し、空きがあれば GPU 常駐と推定した expert も後順位で登録する。既定の prefix pinning では先頭側の領域から登録するため、この変数が有効な経路では `ArenaExpertSource` に登録対象の優先順位を渡す。実際に登録された範囲だけが `pinned()` / `device_alias()` で PCIe 経由の GPU 読み出し対象になり、登録されなかった expert はその範囲として扱われない（`engine/src/program/generate.cpp:8762-8774, 8833-8845`; `engine/include/strata/core/expert_source.hpp:1356-1375`; `engine/src/core/expert_source.cpp:7013-7033`）。

この処理はモデルの expert の配置・読出し経路に関するもので、通常の生成処理や選択順位をこの変数だけで変えるとはコードから確認できない。コードコメントは prefix pinning と byte-identical と記すが、ここでは測定や出力同一性を独立に検証していない（`engine/src/program/generate.cpp:8762-8771`）。

## 値と判定

エンジン起動中、アリーナを開く前に `std::getenv` で一度読み、値全体は parse せず、空でない文字列の先頭文字だけを見る（`engine/src/program/generate.cpp:8774, 8784`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 明示値の判定（各ビルド） | 通常は off。Windows HIP の条件付き既定動作は次節を参照 | 空でなく先頭が `0` 以外。`1`, `true`, `false`, ` 0`, `0anything` のうち前3つと ` 0` は on | 空文字、`0`, `0anything` は off |

大小文字、空白、数値としての妥当性、文字列の残りは検査しない。したがって `false` も先頭が `f` のため有効で、` 0` も先頭が空白のため有効である。明示的な値が空文字ならこの判定は off だが、Windows HIP の既定条件が成立すれば既定動作で on になり得る（`engine/src/program/generate.cpp:8774-8784`）。

## 有効になる条件

- 対象は `o.mmap_experts` のファイル読み出し経路ではなく、`generate.cpp` の `else` 側で使う `ArenaExpertSource` の経路である。エンジンがアリーナを開く前に候補順位を設定する（`engine/src/program/generate.cpp:8621-8628, 8745-8747, 8844, 8871-8872`）。
- 明示的に on と判定されても、expert profile がなければ off となり、stderr に `strata generate: pin by need: off (it needs --expert-profile (the ranking)); the prefix pinning stays` を出す（`engine/src/program/generate.cpp:8784-8792`）。
- layer split、peer GPU、他 GPU の helper cache がある場合も off となり、同じ形式で理由を stderr に出す。判定箇所は `multi_gpu || o.peer_device >= 1` および `o.expert_cache_remote` の正値（`engine/src/program/generate.cpp:8785-8792`）。
- HIP を Windows で使う場合に限り、環境変数が unset または空文字なら、WDDM、discrete GPU での spill、Qwen defaults 0.2.6 でないこと、有効な profile、単一 GPU、peer device なし、helper cache なしをすべて満たすと既定で有効になる。それ以外の build ではこの条件付き既定値は常に false。明示値の有効判定は別途適用される（`engine/src/program/generate.cpp:8775-8784`）。
- `STRATA_ARENA_MMAP` により arena が mmap される場合、および `--shared-expert-arena` の共有 arena では `ArenaExpertSource::open` が pin-by-need の padded layout を選ばない。HIP/Windows の既定判定そのものは共有 arena を条件に含めないが、登録レイアウト側で適用されない（`engine/src/core/expert_source.cpp:6692-6710`）。
- Linux HIP の UMA no-register 状態では、pin-by-need の候補があっても `PinnedArena::ByNeed` は範囲を GPU 登録しない。`STRATA_ARENA_PIN_GIB` のほか、HIP/Linux では engine の no-register flag がこの判定に関わる（`engine/src/core/pinned.cu:611-620, 1213-1238`）。
- `STRATA_ARENA_PIN_GIB` および生成側の pin limit が登録範囲を制限する。登録は候補順で進み、cap 到達または driver の登録拒否でそこで止まる。これは変数を有効にしたことが全候補の登録を保証しないことを意味する（`engine/src/program/generate.cpp:8753-8761, 8871-8874`; `engine/src/core/pinned.cu:1193-1238`）。
- `STRATA_ARENA_LOCK=0` は GPU 用の範囲登録を止める条件ではないが、登録されなかった arena の穴をホスト側で resident lock する処理を無効にする（`engine/src/core/pinned.cu:1243-1270`）。

## 実行時の詳細

値は engine startup の arena setup 時に読み取られ、リクエストごとの再評価や関数内 static cache はない。profile は先に読み込まれており、明示 profile がない場合は pin-by-need を実行しない（`engine/src/program/generate.cpp:6746-6751, 8772-8792`）。設定値をプロセス実行中に変更しても、作成済みの候補順位や登録範囲は変わらない。反映には engine の再起動が必要となる。

有効時は profile の順位列から、GPU cache に入ると見積もった先頭 `skip` 件を除いた残りを候補にし、profile にない expert を layer 順で追加する。これを非 GPU 常駐候補として記録し、最後に先頭 `skip` 件も低い優先度で追加する（`engine/src/program/generate.cpp:8793-8844`）。`STRATA_PIN_BY_NEED_SKIP` が非空なら `atoll` 変換値を 0 以上かつ profile 件数以下に制限して `skip` に使う。非数値や負値は 0、過大値は profile 件数になる。unset / 空文字なら、`--expert-cache N` が正値のとき `N * nibble_max_slot_bytes()`、それ以外では free VRAM から prefill / drafter / pipeline 等の予約分を引いた値の 98%を使い、profile 順に GPU 常駐件数を推定する（`engine/src/program/generate.cpp:8795-8827`）。

`set_pin_priority` の順位は `open()` で blob 単位の範囲へ変換され、隣接 blob は同じ優先 tier 内で結合される。範囲はページ境界に合わせ、順位順にホスト登録される。登録対象・上限により一部だけが登録されることがあり、同じ `pinned()` / `device_alias()` 判定を通じて PCIe share がある layer と expert が決まる（`engine/include/strata/core/expert_source.hpp:1363-1373`; `engine/src/core/expert_source.cpp:6692-6741, 6897-6921, 7013-7033`; `engine/src/core/pinned.cu:1214-1238`）。

Terminal の `strata launch --set STRATA_PIN_BY_NEED=1` は env 名として受け付けられ、launch config の `env` に格納される。engine 起動時には config の env が継承環境に上書きされるため、同じキーを shell 環境にも設定している場合は launch config 側が優先する（`terminal/strata_cli/launch/settings.py:361-377`; `terminal/strata_cli/launch/runner.py:801-806`; `terminal/serve/server.py:4007-4028`）。エンジン側にこの名前の CLI option はなく、直接起動時は環境変数として渡す。

## ログと測定値

- profile 条件などを満たさない場合、理由付きの `pin by need: off (...)` と prefix pinning 継続を stderr に出す（`engine/src/program/generate.cpp:8790-8792`）。
- 有効経路では、GPU 常駐と推定した順位件数と pin 候補数を stderr に出す（`engine/src/program/generate.cpp:8841-8844`）。
- arena の読み込み後、登録範囲数、非 GPU 常駐 expert のうち登録された割合、PCIe share がある layer 数を stderr に出す（`engine/src/program/generate.cpp:8917-8932`）。`expert arena: ...` の note には登録範囲数と MiB、driver が次の範囲を拒否した場合は `the driver refused the next one`、cap 到達時は `the cap was reached` が含まれる（`engine/src/core/pinned.cu:1230-1251`; `engine/src/program/generate.cpp:8934-8939`）。
- 登録候補の値だけを見た性能測定値はここでは記載しない。関連資料 `docs/DETAILS.md:293-297` は Windows の opt-in と登録対象の概要、上限の説明を載せるが、条件付き測定値は示していない。現行コードには Windows HIP の条件付き既定動作もあるため、詳細は上記ソースの条件を基準とする。

## 根拠

- `engine/src/program/generate.cpp:6746-6751, 8621-8628, 8745-8845, 8871-8939`
- `engine/include/strata/core/expert_source.hpp:1356-1375`
- `engine/src/core/expert_source.cpp:6692-6741, 6897-6921, 7013-7033`
- `engine/src/core/pinned.cu:611-629, 1177-1270`
- `terminal/strata_cli/launch/settings.py:361-385`, `terminal/strata_cli/launch/runner.py:801-806`, `terminal/serve/server.py:4007-4028`
- 関連資料との照合: `docs/DETAILS.md:288-297`
