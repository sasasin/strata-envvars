# `STRATA_AUX_CPUS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

`strata generate` の起動時に、CPU pool の worker と host thread 以外の Strata プロセス内スレッドをどの CPU に配置するかを指定します。値の形式は `--aux-cpus` と共通です。Linux では補助 CPU 集合を作り、既存スレッドを移動し、後から作る対象スレッドもその集合へ pin します。これはスレッド配置だけを変更します。

## 値と判定

環境変数の文字列全体を `parse_spec()` に渡します。空白除去、大文字小文字変換、部分一致はしません。

| 値 | 起動時の設定 |
|---|---|
| unset | 空文字相当。起動時 OFF |
| 空文字 | OFF |
| `off` | OFF。小文字の完全一致 |
| `auto` | ON。小文字の完全一致 |
| CPU リスト（例 `24,26`、`24-27`） | ON。数字、カンマ区切り、昇順の範囲を受け付ける |
| その他 | 不正値として起動エラー |

CPU リストは空でない要素からなり、各要素は非負の10進数字または `lo-hi` 形式です。負号、逆順範囲、空要素、文字、区切り以外の文字を含むと失敗します。各数字は最大 `100000` まで許され、範囲は両端を含みます。先頭ゼロは数字として受理されます。重複はソート後に除去されます。空白を含む値（例 `auto `）は受理されません。

不正値の場合、起動処理は stderr に `strata generate: STRATA_AUX_CPUS: --aux-cpus takes off, auto or a CPU list such as 24,26 or 24-27 (got '...')` の形式で出して終了コード 2 を返します。値の妥当性確認と範囲の制限は `include/strata/platform/aux_cpus.hpp:49-80,129-148`、エラー出力は `src/program/generate.cpp:2202-2210` にあります。

## 有効になる条件

- **CLI 優先:** `--aux-cpus` に空でない値が渡された場合、その値が環境変数より優先されます。たとえば `--aux-cpus off` は `STRATA_AUX_CPUS=auto` より優先です。引数が空文字なら環境変数を参照します。CLI 値自体も同じ形式で解析されます（`src/program/generate.cpp:1903-1910,2202-2208`）。
- **Linux:** `auto` はプロセスが使用可能な CPU のうち、host の物理 core の SMT sibling を先に選び、次に pool worker のいない物理 core の CPU を選びます。worker と同じ core の CPU は選びません。core 情報を取得できない CPU も `auto` の集合には入りません。リスト指定は、プロセスが使用可能な CPU に絞り、host CPU と worker CPU を除外します（`include/strata/platform/aux_cpus.hpp:83-126,296-333`）。
- **空集合:** 条件に合う CPU が残らない場合は配置を開始せず、起動ログに `none spare (...)` と出ます。設定が ON でも実際に移動する CPU がない状態です（同 `:329-341`）。
- **他 OS:** 共通の値解析は行われますが、Linux 以外の実装は `set_topology()` で `strata aux cpus: not available on this system` を返し、pin・sweep・restore は何もしません（同 `:344-357`）。

## 実行時の詳細

環境変数は `generate` の起動初期に、pool worker が作られて CPU に pin される前に一度 `getenv()` で読みます。このとき利用可能 CPU 集合を保存します。読み取った値を後で再評価しないため、プロセス実行中に環境を変更しても反映されません（`src/program/generate.cpp:2202-2211`、`include/strata/platform/aux_cpus.hpp:216-231`）。worker の CPU が確定した後に計画を作り、初期設定が ON で計画が空でなければ有効化します（`src/program/generate.cpp:4744-4770`、同 header `:313-341`）。

有効時、Strata が作る補助スレッドは `pin_current_thread()` を呼びます。たとえば adaptive job、prefill helper、PLE/file reader が対象です。pool worker と host thread は owned として登録され、移動対象外です（`src/program/generate.cpp:11387,11936,13119`、`src/prefill/prefill.cpp:456-457,2199,2225,2411,4017`、`src/ngram/ple_reader.cpp:367`、`src/platform/direct_file.cpp:188,315`、`src/kernels/cpu/pool.cpp:461-465`、`src/core/session.cpp:560`）。

Linux では `sweep()` が `/proc/self/task` のスレッドを列挙し、owned でないスレッドを補助 CPU 集合へ移します。初期有効化に加え、serve の各リクエスト開始時に有効状態を設定する処理があります。リクエストの `aux_cpus=0` は移動したスレッドを元の affinity に戻し、`aux_cpus=1` は計画があれば再度有効化します。指定がないリクエストは起動時の状態に戻します。サーバーは `strata_tune.aux_cpus` の boolean または数値 `0`/`1` のみをエンジンへ転送します（`src/program/generate.cpp:10028,10056,10951-10959`、`serve/server.py:1000-1011`）。この per-request 指定は起動時の環境変数の再読込ではありません。

開始時には stderr に `strata aux cpus: threads that are neither pool workers nor the host go to CPUs ...` と計画・状態が出ます。リクエストで状態が変わると `strata serve: aux cpus ON/off for this request` が出ます。環境変数は結果の計算内容を変えるものではなく、Strata の資料もスレッド配置のみを変えると説明しています（`src/program/generate.cpp:4765-4770,10951-10959`、`docs/DETAILS.md:1708-1734`）。

## 根拠

- 値の文法と CPU リスト処理: `include/strata/platform/aux_cpus.hpp:49-80,129-148`
- 起動時の環境変数読取、CLI 優先、設定エラー: `src/program/generate.cpp:1903-1910,2202-2211`
- Linux での CPU 候補選択、スレッド配置、ログ: `include/strata/platform/aux_cpus.hpp:83-126,216-285,296-357`
- pool 作成後の計画設定と初期ログ: `src/program/generate.cpp:4744-4770`
- リクエスト単位の上書きと Python サーバーからの転送: `src/program/generate.cpp:10028,10056,10951-10959`、`serve/server.py:1000-1011`
- 設計説明との照合: `docs/DETAILS.md:1708-1734`
