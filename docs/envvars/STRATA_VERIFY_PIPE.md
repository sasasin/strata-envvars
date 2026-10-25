# `STRATA_VERIFY_PIPE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

SYCL verifier の stepped serve で、CPU 側の `pool` 処理と次の GPU graph segment を重ねるかを制御します。環境変数が有効でも、この重ね合わせが使われるのは次の segment が split point のときだけです。GPU の計算方式や pool が作る計画の内容を選ぶ変数ではなく、host 側で pool を呼ぶタイミングを変えます。

## 値と判定

値全体の parse はせず、`getenv()` の結果の先頭文字だけを見ます。

| 環境変数の状態・値 | 判定 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効（設定値は存在するが、先頭文字は `\0`） |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| その他すべて（例: `1`, `true`, `false`, 空白で始まる文字列） | 有効 |

数値変換、大文字小文字変換、文字列全体の比較はありません。`static const bool` として初回に評価され、そのプロセス内では以後の環境変更は反映されません。

## 有効になる条件

この設定が実際にスレッド並行処理へ進むには、`Verifier::run()` が stepped run に入る必要があります。コード上の条件は `STRATA_VERIFY_STEPPED` が有効、all-resident 経路ではない（`!ar_on()`）、`STRATA_VERIFY_EAGER` が未設定、かつ window 用の segment が存在することです。`STRATA_VERIFY_STEPPED` 自体は `env_on()` で読み、unset・空文字・先頭が `0` の値は無効、それ以外は有効です。

さらに、対象の serve の次 segment が split point（`seg_kind_` が `0`）でなければ、この変数の値による分岐は使われません。split point は `STRATA_VERIFY_SPLIT` が有効な場合に capture されます。この変数は unset で有効、値の先頭文字が `0` なら無効です。split point がない serve、および stepped run でない verifier 経路では `STRATA_VERIFY_PIPE` の設定は動作に影響しません。

`STRATA_VERIFY_STEPPED` が有効で `--remote-expert-opt` が使われていると、`STRATA_VERIFY_PIPE` の分岐に関係なく stepped run は `verify: STRATA_VERIFY_STEPPED does not serve --remote-expert-opt` で失敗します。

## 実行時の詳細

split point でこの設定が有効なら、`run_pool()` を helper `std::thread` で実行します。メインスレッドは pool が flag A を公開するか pool 処理を終えるまで yield し、flag A が上がった後、CPU pool 処理と並行して次の SYCL graph segment を投入します。その後 helper thread を join し、pool の例外があれば `verify: pool: ...` を返します。スレッド作成・graph 投入で例外が起きた場合は `verify: pipelined serve: ...` を返します。

無効の場合、または次 segment が split point でない場合は、メインスレッド上で `run_pool()` を同期実行し、flag A が未公開なら空の計画を設定してから後続処理へ進みます。どちらの経路もその後の `copy_->wait()` と flag B/M の公開を行います。環境変数自体について、値や有効・無効を示す専用ログはありません。

## 根拠

- `sycl/src/core/verify.cpp:101-103`: stepped mode の説明と設定判定 helper `env_on()` の使用。
- `sycl/src/core/verify.cpp:92-95`: `env_on()` は unset・空文字・先頭 `0` を無効とする。
- `sycl/src/core/verify.cpp:1695-1705,1726-1730`: stepped window を segment 化し、`STRATA_VERIFY_SPLIT` が有効なら split point hook を登録する。
- `sycl/src/core/verify.cpp:2039-2043,2055-2058`: stepped run の適用条件と remote expert opt のエラー。
- `sycl/src/core/verify.cpp:2061-2063,2088-2120`: pool 処理、`STRATA_VERIFY_PIPE` の判定、helper thread と同期実行の分岐。
- `sycl/src/core/verify.cpp:2121-2135`: 両経路に続く copy wait、flag 公開、pool/wait 時間の集計。
- `sycl/include/strata/core/verify.hpp:358-368`: stepped mode と serve/split point の役割。

`docs/DETAILS.md` と関連資料にはこの変数固有の説明や測定値を確認できませんでした。そのため性能への影響は記載していません。
