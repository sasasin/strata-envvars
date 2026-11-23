# `ZE_AFFINITY_MASK`

調査対象: Strata main の HEAD 73d4f4196c25a65e02f6b9ef25d354826ce55105（2026-11-23 時点）。

## 役割

Strata はこの変数を独自の GPU 選択設定として直接解釈するのではなく、Intel vendor の GPU 一覧を作るときの可視カード絞り込みに使い、サーバーから SYCL エンジンを起動するときは子プロセス環境に設定または継承します。GPU の候補絞り込みは strata launch のカード役割表示に使われ、--gpu または保存済み GPU 役割で明示されたカードは環境が隠した候補であっても表示対象に残ります（terminal/strata_control/gpu_roles.py:485-518、terminal/strata_cli/launch/cmd.py:425-441）。

サーバーの child_env() は SYCL backend で選んだカードを ZE_AFFINITY_MASK に書き、全カード Off のときは空文字にします。その環境を StrataEngine に渡し、popen() でエンジン子プロセスを起動します（terminal/serve/server.py:3870-3891、terminal/serve/server.py:827-829、terminal/serve/server.py:8873-8878）。ソース内にエンジン C++ 実装がこの名前を読む箇所は見つからず、ここでは外部 SYCL/driver 側での意味は述べません。

## 値と判定

Strata の GPU 候補絞り込み側では env.get("ZE_AFFINITY_MASK") の値を _ordinals() に渡します。未設定 (None) は「環境による絞り込みなし」です。空文字または空白だけは空リストになり、候補をすべて隠す扱いです。設定値はカンマ区切りで分割し、各要素の前後空白を除去して整数 ordinal として読みます。数値以外が一つでもあれば None を返し、Strata はマスクから可視カードを判定できないものとして元のカード一覧を保ちます。負数またはカード数以上の ordinal はそこで処理を打ち切り、それまでに読めた prefix だけを返します（terminal/strata_control/gpu_roles.py:466-482、terminal/strata_control/gpu_roles.py:485-518）。

| 条件 | unset | 設定時に Strata が受け付ける値 | Strata の判定対象にならない値・境界 |
|---|---|---|---|
| Intel vendor のカード一覧 (env_visible) | None。環境による絞り込みなし | 0、1,0、 1 , 0 のような整数 ordinal のカンマ区切り。ordinal はソート済みカード番号リストの位置を指す | 空文字 / 空白だけは空の可視リスト。0,x や x,0 は非数値のため判定不能 (None)。-1 は空リスト、0,-1 は [0]。カード数外の値もそこで打ち切り、0,99 はカードが 2 枚なら [0]。 |

比較は文字列の真偽値判定ではなく、整数への変換です。true、false、0anything、1.0、先頭の + は整数 ordinal として認識されません。要素内の前後空白は無視されますが、カンマ間の空要素（例 0,,1）は非数値扱いです。-0 は整数 0 として扱われます。一方、--1 のように複数の先頭マイナスを持つ文字列は isdigit() 検査を通った後 int() が ValueError を送出します。roles_line() は例外を捕捉して None を返すため、その呼び出しではカード役割行が表示されません（terminal/strata_control/gpu_roles.py:474-480、terminal/strata_cli/launch/cmd.py:431-443）。ここでの値判定は Strata のカード一覧ヘルパーの動作であり、エンジンや外部ライブラリが同じ値をどう解釈するかを示すものではありません。

サーバーの子環境生成側は既存値を parse せず、SYCL の選択順を十進整数のカンマ区切りで上書きします。全カード Off のときは空文字にします。後続の cfg["env"] が同じ名前を指定すれば、その値で上書きされます（terminal/serve/server.py:3873-3891）。

## 有効になる条件

- カード候補の絞り込みは vendor == "intel" の場合だけこの名前を読みます。他 vendor はそれぞれ別の可視デバイス変数を参照し、vendor 不明なら絞り込みません（terminal/strata_control/gpu_roles.py:492-510）。
- strata launch の roles_line() が GPU 役割または --gpu の指定を持ち、hardware catalog を取得できた場合にカード表示用として呼び出されます。指定済みの GPU 番号は keep に含まれるため、マスクの結果にかかわらず表示対象に残ります。この処理は役割表示の一覧を作るもので、保存設定や実際の GPU 選択をこの値で変更しません（terminal/strata_cli/launch/cmd.py:425-441）。
- サーバー側が値を生成するのは cfg["backend"] == "sycl" の経路です。すべて Off なら空文字、それ以外は ordered_gpus(cfg) が返すカード順を設定します。GPU 役割が保存されていると gpu_list() は Main を最後にした役割順を返し、通常の gpu 指定は設定の GPU 番号を使います（terminal/serve/server_parts/engines.py:678-685、terminal/serve/server_parts/engines.py:700-703、terminal/serve/server.py:3778-3789、terminal/serve/server.py:3873-3884）。
- SYCL でも選択カードがなく全 Off にも該当しないときは、この変数を child_env() 内で書き換えず、親プロセス環境から引き継いだ値が残ります。さらに cfg["env"] の同名設定は、Strata が生成した値または継承値より後に適用されます（terminal/serve/server.py:3873-3891）。
- SYCL 以外の backend では、サーバーは全 Off の特別処理を除き、この変数を backend 用に生成しません。親環境または cfg["env"] の値は子環境に残り得ますが、Strata のこのコード経路では Intel vendor の可視カード判定以外に使われません（terminal/serve/server.py:3873-3891、terminal/strata_control/gpu_roles.py:492-510）。

## 実行時の詳細

env_visible() は environ が渡されなければ呼び出し時点の os.environ を使い、値をキャッシュしません。strata launch の roles_line() は visible_cards() を environ 引数なしで呼ぶため、その呼び出し時点のプロセス環境を参照します（terminal/strata_control/gpu_roles.py:485-518、terminal/strata_cli/launch/cmd.py:425-441）。

サーバーは child_env() の呼び出し時に os.environ のコピーを作り、上記条件に応じて値を生成した後、プロファイルの cfg["env"] を反映します。生成された環境辞書はエンジン起動時に popen() の env として渡されます。よって実行中の親環境変更を継続監視する処理はなく、既に起動した子プロセスへ後から変更を反映するコードもありません（terminal/serve/server.py:3870-3891、terminal/serve/server.py:827-829）。

## ログと測定値

この変数だけを理由に出すログや警告はありません。カード役割表示が作られたときは strata launch --plan で「cards     ...」、通常の launch では役割の説明行が出ます。ZE_AFFINITY_MASK の解釈に失敗して roles_line() が None を返すと、この行は出ません（terminal/strata_cli/launch/cmd.py:920-923、terminal/strata_cli/launch/cmd.py:929-932、terminal/strata_cli/launch/cmd.py:431-443）。Strata 資料にこの変数に関する測定値はありません。

## 根拠

- terminal/strata_control/gpu_roles.py:466-518 — 値の ordinal 変換、Intel vendor での読み取り、空・無効値・範囲外の処理、可視カードの絞り込み。
- terminal/strata_cli/launch/cmd.py:425-443 — roles_line() の呼び出し条件、明示 GPU を keep する処理、カード役割表示。
- terminal/serve/server.py:3870-3925 — 子環境の生成、SYCL のマスク設定、全 Off 時の空文字、cfg["env"] による後勝ち上書き。
- terminal/serve/server_parts/engines.py:678-703、terminal/serve/server.py:3778-3829 — GPU リストと順序、全 Off 判定。
- terminal/serve/server.py:827-829、terminal/serve/server.py:8873-8885 — 生成した環境辞書をエンジン起動へ渡す経路。

docs/DETAILS.md および Intel 関連資料も確認しましたが、この変数についての Strata 側の値解釈を追加で裏付ける記述は見つかりませんでした。調査範囲は上記 commit の Strata 所有ソースです。
