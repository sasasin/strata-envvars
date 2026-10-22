# `STRATA_AUX_CPUS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`strata generate` の補助スレッドをどのCPUに置くかを指定します。対象はCPUプールのworkerでもhost threadでもないエンジンスレッドです。たとえばadaptive tier、prefill helper、ファイル読み込みworker、PLE readerなど、生成コードが `pin_current_thread()` を呼ぶスレッドが含まれます。Linuxではこれらのスレッドを、workerとhostのCPUを避けて選んだCPU集合へ移します。スレッド配置だけを変え、生成結果は変えない設計です。

この名前を環境から読む実装は `src/program/generate.cpp` の起動処理1箇所です。Qwen3.6用の別engineにはこの配置処理は適用されません（`docs/DETAILS.md` の説明も参照）。

## 値と判定

値は真偽値や数値ではなく、`off`、`auto`、またはCPU番号のリストとして完全一致で判定されます。大文字小文字や前後の空白は正規化されません。

| 値 | 判定と起動時の動作 |
|---|---|
| 環境変数未設定 | CLI指定もなければ空文字扱いとなり、起動時は無効。Linuxでは配置計画自体は作り、serveリクエストから後で有効にできる。 |
| 空文字 | `off` と同じ。 |
| `off` | 起動時は無効。 |
| `auto` | 起動時に有効。Linuxではhostの物理コアのSMT siblingを先に選び、続いてworkerが使っていない物理コアのCPUを選ぶ。 |
| CPUリスト（例: `24,26`、`24-27`） | 起動時に有効。Linuxでは指定リストからhost CPU、pool workerのCPU、プロセスが使用できないCPUを除いた集合を使う。 |
| その他 | 不正値。`--aux-cpus takes off, auto or a CPU list such as 24,26 or 24-27 (got '…')` を標準エラーに出し、起動処理は終了コード2で失敗する。 |

リストは10進の非負整数と昇順範囲をカンマでつなぎます。空要素、負数、文字、逆順範囲、空リストは拒否されます。重複は除去され、結果は昇順です。各数値が100000を超える入力も拒否されます。たとえば `1,3-5` は有効ですが、`1, 3`、`3-1`、`1,` は無効です。

起動時の優先順位は `--aux-cpus` の非空値、次に `STRATA_AUX_CPUS`、最後に空文字（無効）です。CLI値は引数解析時にも検証されます。CLI値が `off` なら環境変数を上書きします。一方、CLIに明示的な空文字を渡した場合は、後続の選択処理が空文字を「未指定」と同様に扱うため、設定されていれば環境変数の値が使われます。

## 有効になる条件

- 実際のスレッド affinity 設定はLinuxのみです。他OSでも値の構文検査は行われますが、配置関数は何もせず、計画は空です。
- Linuxでは起動時にプロセスが使用可能なCPU集合を記録し、pool workerとhost threadのCPUが分かった後に計画を作ります。`auto` はsysfsでpackage/coreを判別できるCPUだけを使います。
- `auto` はhostのSMT siblingを優先し、その後workerと同じ物理コアに属さないCPUを選びます。明示リストもhost CPUとworker CPUを除外します。使用可能なCPUが残らない場合は計画が空になり、機能は有効になりません。
- 起動時に `off` でもLinuxでは計画を保持します。serveの `strata_tune.aux_cpus` に `1` があれば、そのリクエストで `auto` 計画を有効にできます。計画のないOSやCPU構成では要求しても有効化されません。
- `strata_tune.aux_cpus` はサーバーが真偽値または数値の0/1だけをエンジンへ渡し、エンジン側は `atoi(...) != 0` で判定します。リクエストにこのキーがなければ起動時の有効状態に戻し、`0` は移動済みスレッドの元のaffinityを復元します。リクエストごとにスレッドを再走査します。
- `STRATA_ADAPT_JOB_CPU` で個別CPUを指定されたadaptive tierのjob threadは、この配置よりそちらの指定が優先されます。`STRATA_AUX_STAGER=0` の場合、prefill copy threadは `pin_current_thread()` を呼ばず、aux CPUへ移りません。

## 実行時の詳細

起動処理はpool構築より前に環境変数を読み、初期affinityからプロセスの許可CPU集合を記録します。CLIの値が空なら `getenv("STRATA_AUX_CPUS")` を読みます。変数の値は起動時に一度だけ読み取られ、以降に環境を書き換えても再評価されません。pool構築後、hostとworkerのCPUおよびLinux sysfsのcore topologyから配置先を計算します。

起動時に有効で配置先が空でなければ、既に存在する非ownedスレッドを `/proc/self/task` から走査して移し、後から作られる対象スレッドは `pin_current_thread()` で移します。pool workerとhost threadはownedとして除外されます。serveではリクエストの開始ごとに有効状態を設定し、有効化時に再走査、無効化時に移動前のaffinityを復元します。

Linuxの起動ログは `strata aux cpus: threads that are neither pool workers nor the host go to CPUs …` です。配置先がない場合は理由を含む `none spare (...)` を表示します。serveで状態が変わると `strata serve: aux cpus ON/off for this request` を標準エラーに出します。非Linuxでは `strata aux cpus: not available on this system` を返します。

## 根拠

- 候補変数のCLI説明とCLI優先の仕様: `src/program/generate.cpp:525-526,1029-1035,2513-2520`。
- 起動時のCLI/environment選択、エラーと終了: `src/program/generate.cpp:2874-2883`。
- 全環境変数読み取り箇所: `src/program/generate.cpp:2878`。ソース全体検索では他の `getenv` 等による `STRATA_AUX_CPUS` 読み取りはありません。
- 値の構文、空文字、`off`、`auto`、リスト解析: `include/strata/platform/aux_cpus.hpp:50-82,137-149`。
- 許可CPUの記録、スレッド走査、affinity設定、復元: `include/strata/platform/aux_cpus.hpp:179-213,218-289`。
- 配置先計画と起動ログ: `include/strata/platform/aux_cpus.hpp:84-127,375-405,407-422`; 呼び出し箇所 `src/program/generate.cpp:5904-5908`。
- リクエストごとの値の解析と切替: `src/program/generate.cpp:12162-12164,12198,13799-13808`; Pythonサーバーでの転送条件 `serve/server.py:1404-1420` および設定許可キー `serve/server.py:7738-7742`。
- 補助スレッドの例と例外、別engineの扱いとの照合: `docs/DETAILS.md:2142-2169`。この資料の説明は上記の現行ソースと一致します。
