# `STRATA_AUX_CPUS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata generate` の起動時に、CPU pool の worker と host thread 以外のスレッドをどの論理 CPU で動かすか指定する。Linux では CPU affinity を設定する機能で、計算結果を変える設定ではない。`--aux-cpus` と同じ値を受け取り、空でない CLI 値が環境変数より優先される。環境変数の値は起動時のベース設定となり、serve ではリクエストごとの `strata_tune.aux_cpus` がそのリクエスト中の状態を上書きできる（`engine/src/program/generate.cpp:4715-4724, 21431-21440`、`terminal/serve/server.py:1388-1404`）。

環境変数名の実際の読み取りは `generate.cpp` にあり、Linux の NUMA card-node 判定にも参照される。直接の `getenv` は起動中に2箇所で行われる。後者が affinity 設定の本体で、前者は Linux かつ Metal 以外のビルドで複数 NUMA node を扱うとき、明示的な CPU list があるかを card-node 判定に伝える（`engine/src/program/generate.cpp:4615-4625, 4655-4665, 4715-4724`）。

## 値と判定

空でない CLI 値がある場合はそれを使い、環境変数を読み取らない。CLI 値が空（引数なし時の既定値、または空文字引数）の場合は環境変数を参照する。環境変数が未設定または空文字なら `parse_spec` に空文字列が渡り、起動時は off となる。`off` と `auto` は小文字の完全一致で判定され、その他は CPU list として全体を解析する（`engine/src/program/generate.cpp:3956-3964, 4715-4724`、`engine/include/strata/platform/aux_cpus.hpp:137-149`）。

| 条件 | unset / 空文字 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| 全プラットフォームでの値解析 | off | `auto`、または CPU list（例 `24,26`、`24-27`） | 大文字小文字違いの `AUTO` / `OFF`、`true` / `false`、`0anything`、空白を含む値、空要素や逆順 range など不正な list |
| Linux で affinity を適用 | 上と同じ | list の各 ID がプロセスの許可 CPU に含まれ、host / worker の CPU 以外なら計画に残る | 構文不正は起動失敗。構文が正しくても許可 CPU 外、host / worker CPU の ID は除外され、全て除外されれば空の計画 |
| Linux 以外 | 上と同じ | 値の構文解析のみ成功する | 構文不正は起動失敗。構文が有効でも affinity は適用されない |

list は10進数字、カンマ区切り、または両端を含む `lo-hi` range で構成する。数字は最大 `100000`、range は `hi >= lo` が必要。空要素、負数、文字、余分な区切り、空白は受理されない。list はソートされ重複が除かれる。値 `0` や `1` は真偽値でなく CPU ID である。`auto` / `off` / list の比較は大文字小文字を区別する（`engine/include/strata/platform/aux_cpus.hpp:50-81, 137-149`）。

環境変数由来の不正値は `strata generate: STRATA_AUX_CPUS: ...` を stderr に出し、終了コード `2` で起動を中止する。CLI 由来の不正値は引数解析時に `strata generate: ...` を出し、同じく `2` で終了する（`engine/src/program/generate.cpp:3956-3963, 4717-4724`）。

## 有効になる条件

- affinity の設定・スレッド移動が動作するのは Linux。Linux 以外では値を解析するが、`configure`、`set_enabled`、`pin_current_thread` は実質 no-op で、起動時の案内は `strata aux cpus: not available on this system` となる（`engine/include/strata/platform/aux_cpus.hpp:151, 407-424`）。
- `auto` は pool の worker CPU と host CPU が確定した後、プロセスが使える CPU の topology を調べて計画を作る。host の SMT sibling を先に使い、その後 worker と物理 core を共有しない core の CPU を加える。明示 list はプロセスが使える CPU から host と worker の CPU を除いたものを使う。計画が空なら実際の移動は行われず、起動ログに理由が出る（`engine/include/strata/platform/aux_cpus.hpp:84-127, 378-405`）。
- `auto` の計画には sysfs で package/core が判別できる CPU が必要。明示 list は sysfs topology ではなく許可 CPU かどうかで絞る（`engine/include/strata/platform/aux_cpus.hpp:87-115, 118-127, 358-372`）。
- 起動時に off でも serve の request tuning で `aux_cpus=1` を指定すれば有効化を試み、`0` なら移動済み thread の元 affinity を戻す。計画が空なら `1` を指定しても有効にはならない（`engine/src/program/generate.cpp:21431-21440`、`engine/include/strata/platform/aux_cpus.hpp:265-287`）。
- Linux の複数 NUMA node 判定（`__linux__` かつ `!STRATA_GPU_METAL`）では、空でない `STRATA_AUX_CPUS` が正確に `auto` / `off` 以外なら「CPU list が指定された」と扱い、card-node CPU 制限の自動適用を見送る理由になる。これは値の構文検証より先に行われるため、不正値でも一時的にこの判定に影響した後、通常の設定箇所で起動エラーになる（`engine/src/program/generate.cpp:4615-4625, 4655-4679, 4715-4724`、`engine/include/strata/kernels/cpu/card_node.hpp:148`）。

## 実行時の詳細

設定本体は pool / host thread の pinning 前に、`configure` が呼び出し元 thread の許可 CPU set を保存して値を解析する。pool 構築後に `set_topology` が CPU topology と worker CPU を使って計画を作り、設定が on かつ計画が空でなければその場で既存の非 owned thread を sweep して移動する。Strata が作る補助 thread は `pin_current_thread()` で自分を移動する。Linux 実装では `/proc/self/task` を走査するため、対象は同一プロセス内の thread である（`engine/include/strata/platform/aux_cpus.hpp:218-263, 375-405`、呼び出し例 `engine/src/program/generate.cpp:9003-9041`）。

環境変数はプロセス起動中に読み取られ、継続的な再読込や環境変数値の cache はない。ただし Linux / 非 Metal の NUMA 判定箇所と affinity 設定箇所が別々に `getenv` を呼ぶ。request ごとの設定は環境変数を再読まず、serve ループ内で起動時の enabled 状態（関数内 `static`）または request 値を使う。request ごとに有効なら thread sweep を実行し、新しく作られた thread を拾う。off に切り替えるとこの機能が移動させた thread を保存済みの affinity に戻す（`engine/src/program/generate.cpp:4655-4665, 4715-4724, 21431-21440`、`engine/include/strata/platform/aux_cpus.hpp:265-287`）。

`terminal/serve/server.py` は `strata_tune.aux_cpus` が bool または数値 `0` / `1` のときだけ `aux_cpus=0|1` を engine request に付ける。それ以外は転送しない。engine は request キーの数値を `atoi(...) != 0` で真偽にするが、server 経由では上記の値に制限される（`terminal/serve/server.py:1388-1404`、`engine/src/program/generate.cpp:18859-18866, 18921-18927`）。

## ログと測定値

起動時は stderr に `strata aux cpus: threads that are neither pool workers nor the host go to CPUs ...` を出す。計画が空なら `none spare (every CPU is the host's, a worker's or shares a core with a worker or has no known core) (nothing to do)` が続く。off なら `(off at start; a request's aux_cpus=1 turns it on)`、on なら `(on; N threads placed so far)` が続く（`engine/include/strata/platform/aux_cpus.hpp:393-405`）。

serve のリクエストで状態が切り替わったときは `strata serve: aux cpus ON for this request` または `strata serve: aux cpus off for this request` を stderr に出す。起動時に計画が空の状態で `1` を求めた場合は、実状態に応じて ` (asked for, but no CPU is spare: see the start-up line)` が付く（`engine/src/program/generate.cpp:21431-21440`）。

`docs/DETAILS.md:1433-1447` の説明は Linux 限定、auto/list/off の概略、serve の per-request override と一致する。そこに記載された性能値は特定の測定環境に限られるため、この環境変数の一般的な効果としては扱わない。

## 根拠

- `engine/src/program/generate.cpp:3956-3964` — `--aux-cpus` の取得と parse。
- `engine/src/program/generate.cpp:4615-4679` — Linux / 非 Metal の NUMA 判定における変数参照と list 指定の扱い。
- `engine/src/program/generate.cpp:4715-4724` — CLI と環境変数の優先順位、設定、無効値の stderr と終了。
- `engine/src/program/generate.cpp:9003-9041` — pool 構築後の plan 計算・起動時ログ。
- `engine/include/strata/platform/aux_cpus.hpp:50-81, 137-149` — CPU list と `off` / `auto` の構文・値判定。
- `engine/include/strata/platform/aux_cpus.hpp:218-263, 265-287, 375-424` — Linux の設定・thread 移動・復元、および非 Linux の no-op。
- `engine/src/program/generate.cpp:18859-18866, 18921-18927, 21431-21440`、`terminal/serve/server.py:1388-1404` — serve request の per-request override と転送。
- `docs/DETAILS.md:1433-1447` — 実装説明との照合（性能値はこの文書では一般化しない）。
