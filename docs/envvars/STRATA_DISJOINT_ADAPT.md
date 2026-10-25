# `STRATA_DISJOINT_ADAPT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

適応型 GPU expert cache が次に常駐させる expert を選ぶとき、helper GPU の `RemoteExperts` cache が現在保持する `(layer, expert)` を候補から除外します。これにより primary 側の適応 cache が helper と同じ expert を追加するのを避けます。既定では無効です。

判定と候補選定は CUDA 実装 `src/program/generate.cpp` と SYCL 実装 `sycl/src/program/generate.cpp` の両方にあります。CLI の generate 経路と serve 経路（通常の同期適応および非同期適応）の候補選定に適用されます。

## 値と判定

値は `std::getenv()` で読み、`std::atoi(v) != 0` で判定します。文字列全体の妥当性検査はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（`atoi("")` は 0） |
| 数値として 0 | 無効。符号や先行空白を含む 0 も無効 |
| 数値として 0 以外 | 有効。負数も 0 以外として有効 |
| 数字で始まらない文字列 | `atoi` が 0 を返すため無効 |
| 数字の後ろに文字が続く文字列 | 数字部分が 0 以外なら有効（例: `1abc`） |

数値は `int` に変換され、追加の範囲制限や clamp はありません。変数は generate 初期化部のローカル `const bool` として一度だけ評価されるため、その後の環境変更は実行中の判定に反映されません。反映にはプロセス再起動が必要です。

## 有効になる条件

- `--adapt-every` と `--adapt-swaps` により適応型 GPU cache が有効で、適応候補を作る経路を実行すること。候補選定は、layer ごとに現在 primary cache にない expert（`r[e] < 0`）のうち利用回数が `u[e] >= 2.0f` のものを対象とします。
- 少なくとも一つの remote helper cache が初期化され、その cache に候補 expert が現在 resident であること。helper がない場合や、その expert を保持していない場合は、この変数による候補除外は起きません。
- `STRATA_DISJOINT_ADAPT` が有効と判定されること。

候補への追加時に `helper_holds(l, e)` を呼び、true ならその expert を候補 vector に入れません。その後の候補順位付け、入れ替え利得判定、swap 数上限の処理は既存のままです。

## 実行時の詳細

`helper_holds` は環境変数が無効なら即座に false を返します。有効なら `drive.d.remote[0..remote_count)` を順に調べ、いずれかの `RemoteExperts::holds(l, e)` が true なら候補を除外します。`holds` は helper の現在の `ExpertCache::slot_of(layer, expert) >= 0` を返すため、起動時に複製した所有 mask ではなく、入れ替え後の cache 状態が候補評価時に参照されます。

候補選定箇所ごとの既存条件には差があります。

- serve の通常適応（CUDA/SYCL）は、helper 保持に加えて、peer cache が保持する expert と `remote_opt` が所有する expert も別々に候補から除外します。
- serve の非同期適応（CUDA/SYCL）では `helper_holds` を使って helper 保持を除外します。
- CLI generate の適応（CUDA/SYCL）でも `helper_holds` を使います。

この環境変数自体はログを出さず、適応機能の有効/無効や適応頻度を変更しません。helper が保持する expert が候補から外れることで、同じ layer の別の候補が選ばれる場合があります。候補がなくなればその expert の追加は行われません。

## 文書との照合

`docs/DISJOINT_EXPERT_CACHE.md` は既定 OFF、server と CLI の双方で helper 所有 expert を promotion 候補から外すこと、および `RemoteExperts::holds` による動的な確認を説明しており、調査対象 HEAD の実装と一致します。同文書の性能表は別の歴史的な複合ビルドでの値であり、同文書自身が pure-upstream port の測定値ではないと明記しています。そのため、この HEAD での速度向上や性能値としては扱えません。`docs/DETAILS.md` にはこの変数の説明を確認できませんでした。

## 根拠

- `src/program/generate.cpp:5467-5480`: `atoi` による一度限りの判定、helper cache 探索、remote helper の登録。
- `src/program/generate.cpp:8341-8364,8565-8586,12870-12904`: serve 通常適応、serve 非同期適応、CLI generate の候補選定。
- `sycl/src/program/generate.cpp:5042-5055,7817-7839,8045-8065,12173-12193`: SYCL の同等の判定と候補選定。
- `include/strata/core/remote_experts.hpp:41-43`: `RemoteExperts::holds` が helper cache の `slot_of` を調べる実装。
- `src/program/generate.cpp:579-581,8239-8240,12828-12829`: 適応周期・swap 数に基づく適応候補機能の設定。
- `docs/DISJOINT_EXPERT_CACHE.md:13-19,30-33,35-48`: 既定値、意図、過去測定の条件と適用範囲。
