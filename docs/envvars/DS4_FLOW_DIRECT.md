# `DS4_FLOW_DIRECT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`DS4_FLOW_DIRECT` は、DS4 の prompt expert flow で、読み出した expert の各 part を flow ring の slot へ直接書き込むか、host staging buffer を経由してから GPU へコピーするかを選びます。これは `STRATA_METAL` が定義されたビルドだけで読み取られます。環境変数は flow を有効化しません。flow が別の条件で有効になった後に、単一 member layer の item に対する経路を選びます。

## 値と判定

値は `std::atoi` で整数へ変換し、変換結果が 0 かどうかで判定します。文字列全体の妥当性検証はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 有効（既定値）。`cp->direct` を `true` にする |
| 空文字 | 無効。`atoi("")` は 0 |
| 数値変換結果が 0 | 無効。例: `0`, `00`, `abc`, `0abc` |
| 数値変換結果が 0 以外 | 有効。例: `1`, `-1`, `1abc`, ` 1` |

末尾に数値以外が続いても、`atoi` が先頭部分から得た値で判定します。値に範囲制限や fallback はありません。設定値は CLI 引数や他の環境変数で上書きされません。なお、`DS4_FLOW=0` などで flow が有効にならない場合、この設定による経路選択も行われません。

根拠: `src/dsv41/ds4_model.cu:3093-3098`。

## 有効になる条件

- Strata の `STRATA_METAL` ビルドであること。環境変数の読み取りと `cp->direct` への代入が `#if defined(STRATA_METAL)` 内にあります。CUDA/HIP ビルドではこの変数を読みません。
- DS4 のモデル初期化が、expert をファイルから読む `file_experts` 経路に入ること。flow の設定コード全体が `if (file_experts)` 内にあります。
- 対象 chunk に ring があり、`fl` が真になること。`fl` はまず `DS4_FLOW`（未設定なら ON、設定時は `atoi != 0`）で決まり、その device に属する各非 MTP layer が MXFP4 であることを要求します。tensor parallel の layer は追加で `DS4_FLOW_TP` が非 0 で、down の block alignment 条件を満たす必要があります。
- item 単位の直接経路はさらに `l.nm == 1` を要求し、`in_ram && copy_mode` の item では使いません。したがって、flow が有効でも multi-member layer や該当する RAM copy item は staging 経由です。

`DS4_FLOW_DIRECT` を 0 にしても flow 自体は停止しません。flow の有効条件は `src/dsv41/ds4_model.cu:3064-3098`、item ごとの適用条件は `src/dsv41/ds4_model.cu:3812-3863` にあります。

## 実行時の詳細

モデル初期化中、各対象 chunk の `fl` が真のときに環境変数を読み、値を `Chunk::direct` に保存します。これはリクエストごとの読み取りではありません。プロセス中に環境を変更しても、既に初期化された chunk の値は再評価されません。対象 chunk がなければその読み取り箇所には到達しません (`src/dsv41/ds4_model.cu:3071-3100`)。

flow item の作成時、`Chunk::direct` が真で単一 member layer かつ `in_ram && copy_mode` でなければ item に direct flag を立て、staging slot を割り当てずに返します (`src/dsv41/ds4_model.cu:3855-3863`)。`flow_pump()` はその item 用に ring の再利用可能性を確認し、各 expert part の I/O job の宛先を ring slot 内に設定して reader queue に渡します。Metal では ring の device address から `strata::gpu::host_view()` を得た host view を宛先に使います (`src/dsv41/ds4_model.cu:3980-4028`)。

direct flag が立たない item は staging slot に読み込みます。読み込み完了後、別の経路で staging から ring へ CUDA copy を queue し、`ring_fill` event を記録します。direct item は ring への読み込み後に同 event を記録し、通常の flow 計算経路に合流します (`src/dsv41/ds4_model.cu:4029-4072,4083-4114`)。

この変数専用のログはありません。verbose または `DS4_FLOW_STATS` が有効な場合は prompt stream の一般統計が stderr に出ますが、direct/staging の選択値は表示されません (`src/dsv41/ds4_model.cu:9487-9512`)。読み出しに失敗すると `flow_pump()` は `reading layer <番号> expert <番号> from the model's files failed` をエラーとして返します。これは I/O の失敗経路であり、direct 選択だけに固有の警告や終了動作は確認できません (`src/dsv41/ds4_model.cu:4083-4089`)。

## 根拠

- 全候補名参照と実読み取り: `src/dsv41/ds4_model.cu:3096-3098`。本 commit の Strata ソース内で `DS4_FLOW_DIRECT` の参照はこの 1 箇所。
- flow の初期化条件と関連変数: `src/dsv41/ds4_model.cu:3001-3003,3064-3120`。
- chunk/item の direct flag と適用条件: `src/dsv41/ds4_model.cu:634-699,3812-3863`。
- direct read の宛先と staging / DMA 経路: `src/dsv41/ds4_model.cu:3980-4072,4083-4114`。
- flow の実行および一般統計ログ: `src/dsv41/ds4_model.cu:4120-4175,9487-9512`。

`docs/DETAILS.md` には `DS4_FLOW_DIRECT` の説明は見つかりませんでした。ソースで確認できた挙動のみを記載し、性能差は主張していません。
