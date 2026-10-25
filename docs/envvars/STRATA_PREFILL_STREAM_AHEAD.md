# `STRATA_PREFILL_STREAM_AHEAD`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

CUDA の prompt prefill で、現在の layer の expert を routed-only staging ring に先行 upload するスケジュールを選びます。既定では有効です。無効にすると、従来の routed-only upload schedule に戻ります。加えて、有効時は router の出力を CPU に読み戻した後に shared expert を実行し、CPU grouping と最初の expert upload に重ねます。

これは expert の割り当てや router の結果を変える設定ではなく、CUDA prefill 内の upload と shared expert 実行の順序を変える設定です。Strata のソースにはこの名前の読み取りは CUDA 実装の `src/prefill/prefill.cpp` だけにあります。SYCL の同ファイルには読み取りがなく、Metal 実装にもありません。

## 値と判定

値は `std::atoi()` で整数に変換し、結果が 0 かどうかで判定します。文字列全体の妥当性検査はありません。

| 値 | 判定 |
|---|---|
| unset | 有効（既定） |
| `0`、空文字、`abc`、`0abc` | 無効（`atoi` の結果が 0） |
| 整数として 0 以外に変換される値（例: `1`, `-1`, `2`, `1abc`） | 有効 |

空白や符号の扱いも `atoi()` による変換に従います。先頭の整数部分が 0 なら後続文字にかかわらず無効、整数部分が非 0 なら有効です。値の範囲制限はありません。

読み取り結果は `stream_ahead_enabled()` 内の関数ローカル `static const bool` に保存されます。初回評価後にプロセス環境を変更しても再評価されません。

根拠: `src/prefill/prefill.cpp:124-131`。

## 有効になる条件

環境変数が有効でも、chunk が `stream_all` 経路を使う場合はこの設定による routed-only staging の分岐を通りません。`stream_all` は、ring slot 数が `STAGE`（8）より多く、chunk token 数が `stream_all_min()` 以上で、`ExpertSource` がある場合に成立します。`stream_all_min()` は既定 1024 tokens で、別変数 `STRATA_PREFILL_STREAM_MIN` による変更があります。

そのほかの chunk、すなわち `!stream_all` では CUDA prefill の routed-only 経路で設定を参照します。この経路では resident expert は staging slot を使わず、非 resident expert が upload 対象です。別環境変数 `STRATA_PREFILL_STREAM_MIN`、ring のサイズ、expert source の有無が間接的にどちらの経路になるかを決めます。

根拠: `src/prefill/prefill.cpp:122-123,164-168,2340-2342,3953-3977`。

## 実行時の詳細

CUDA prefill は router 結果の expert 順 `order` に沿って非 resident expert を stage します。stage された expert blob は host から device へコピーされ、copy 完了 event を待ってから compute stream で使われます。ring は 8 slot です。

- 有効時は、まだ pending の実転送数が 8 未満である間、resident entry を飛ばしながら次の expert を先行 stage します。expert の計算を進めるたび pending 数を減らします。これにより、単に `order` 内の現在位置から 7 entry 先までに限るのではなく、空いた ring slot に応じて upload を前倒しします。
- 無効時は、`staged <= j + 7` の範囲で次を stage します。`j` は現在計算する expert の位置、`staged` は次の stage 位置です。この旧スケジュールは resident entry も位置として lookahead に数えます。

有効時には shared expert の計算も順序が変わります。通常は router の完了後、CPU への routing readback より前に実行します。有効時はこれを readback の後、host grouping より前に移し、routing の CPU grouping と routed-only 経路の初期 expert upload に重ねる構成です。`stream_all` では `defer_shared` が false となるため、この移動は適用されません。

この環境変数専用のログ出力は確認できません。実行結果として観測できるのは、主に prefill のコピーと計算の重なり方、および chunk の所要時間です。ソースコメントに「以前の routed-only upload schedule (A/B)」への切替として記されていますが、この変数の性能差を示す測定条件・値はコードコメントや `docs/DETAILS.md` では確認できません。速度向上や出力同一性はここでは断定しません。

根拠: `src/prefill/prefill.cpp:3019-3022,3245-3249,3771-3821,3953-3977`。

## 根拠

- 値の読み取りと既定: `src/prefill/prefill.cpp:124-131`。
- chunk が全expert streaming経路に入る条件: `src/prefill/prefill.cpp:2340-2342`。
- shared expert の実行順: `src/prefill/prefill.cpp:3019-3022,3245-3249`。
- staging と copy event: `src/prefill/prefill.cpp:3794-3821`。
- routed-only upload の先行範囲と expert compute: `src/prefill/prefill.cpp:3953-3977`。
- docs照合: `docs/DETAILS.md` と `docs/STRIX_HALO.md` に prefill の一般的な streaming 説明はあるが、`STRATA_PREFILL_STREAM_AHEAD` の説明やこの切替に関する測定値は見つからなかった。
