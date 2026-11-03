# `STRATA_STACK_ISOLATE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Windows HIP 版 `strata` の起動時に、GPU に登録する pinned expert arena の GPU alias と、エンジンの stack や後から確保するメモリのアドレスが重なるのを避けるための起動経路を制御します。有効時はプロセスの 1 TiB 未満にある空きアドレス空間を予約し、エンジンを新しいスレッドで実行します。これはメモリを commit する処理ではありません。

この仕組みは `STRATA_USE_HIP` と `_WIN32` の両方が定義されたときにコンパイルされます。それ以外の OS/backend では、この環境変数を読む `main` の実装はありません。ビルド定義と実行ファイルの構成は `CMakeLists.txt:893-903`、条件付き実装は `src/program/generate.cpp:20673-20682,20716-20733` にあります。

## 値と判定

コードは値を数値や真偽値として parse せず、先頭文字だけを検査します。

| 値 | 起動時の処理 |
|---|---|
| 未設定 | 有効。1 TiB 未満の予約を試み、新しいスレッドでエンジンを実行する |
| 空文字 | 有効。設定値の先頭は終端文字 `\0` であり、`'0'` ではない |
| 先頭文字が `0` | 無効。例: `0`, `0anything`。予約せず、最初のスレッドでエンジンを実行する |
| その他の設定値 | 有効。例: `1`, `true`, `false`, `anything`。文字列全体は検査しない |

大文字小文字、空白、数値としての妥当性、2 文字目以降は判定に影響しません。値の判定と分岐は `src/program/generate.cpp:20717-20732` にあります。

## 有効になる条件

- Windows HIP ビルドであることが必要です。実装全体が `#if defined(STRATA_USE_HIP) && defined(_WIN32)` 内にあります（`src/program/generate.cpp:20673`）。
- 判定は CLI 引数の解析やエンジンモードの選択より先に `main` で行われます。したがって、この wrapper を通る起動では CLI 引数による上書きはなく、通常実行・サーバー起動などのモードに関係なく同じ起動処理が適用されます（`src/program/generate.cpp:20716-20733`）。
- `STRATA_STACK_ISOLATE` を参照する Strata ソースはこの箇所だけです。別環境変数による優先順位や連動条件はありません（`src/program/generate.cpp:20717`）。
- 予約は空き領域ごとの best effort です。`VirtualQuery` で空きと判定された領域を allocation granularity に合わせて `VirtualAlloc(MEM_RESERVE)` します。予約に失敗した領域は記録されず、失敗だけを理由に起動を中止したり警告したりする処理はありません（`src/program/generate.cpp:20693-20714`）。

## 実行時の詳細

環境変数は `main` の呼び出しごとに一度読みます。`iso == nullptr || iso[0] != '0'` なら、最初のスレッドの stack 範囲を `set_idle_thread_stack` に渡し、1 TiB 未満の空き領域の予約を `set_held_address_space` に登録した後、`CreateThread` で `engine_main` を起動します。新しいスレッドの完了を待ち、戻り値をプロセスの終了コードとして返します。プロセス起動後に環境を書き換えても、この分岐には反映されません（`src/program/generate.cpp:20717-20729`）。

`src/core/pinned.cu` の `claim_alias` は、登録対象の GPU alias と重なる領域を調べます。起動時に予約した領域と、エンジンが待機する最初のスレッドの stack は既知の領域として走査を飛ばします。その他の使用中メモリと重なる場合、alias の予約を取り消して理由を返します（`src/core/pinned.cu:636-701`）。登録後にこの確認が失敗すると、Strata は範囲の登録を解除し、stderr に `strata pin: ...; that range stays unregistered (#3431)` と出して、その範囲を未登録として扱います（`src/core/pinned.cu:715-729`）。arena の登録全体が失敗した場合は、呼び出し側の通常の失敗処理に進み、部分登録・resident lock などの状態を記録します（`src/core/pinned.cu:779-854`）。

`CreateThread` に失敗した場合は待機 stack の登録を解除し、同じスレッドで `engine_main` を実行します。先に行ったアドレス予約は解除されません（`src/program/generate.cpp:20722-20732`）。

## 根拠

- 値の読み取りと起動分岐: `src/program/generate.cpp:20716-20733`
- 1 TiB 未満の予約方法: `src/program/generate.cpp:20693-20714`
- Windows HIP のみの条件と目的: `src/program/generate.cpp:20673-20682`
- GPU alias の走査と使用中領域の判定: `src/core/pinned.cu:627-703`
- 衝突時の登録解除と stderr 出力: `src/core/pinned.cu:713-729`
- arena 登録失敗後の処理: `src/core/pinned.cu:779-854`
- 同機能の説明資料: `docs/AMD_HIP.md:154-161`。実装と同様に Windows HIP の pinned arena を扱い、`STRATA_STACK_ISOLATE=0` で予約を無効にできると説明しています。
