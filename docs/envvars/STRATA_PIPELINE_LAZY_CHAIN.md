# `STRATA_PIPELINE_LAZY_CHAIN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`--pipeline-windows 2` のサーバー復号ループで、次の投機ウィンドウ用に MTP drafter の chain を一度に全段実行する代わりに、すでに届いた出力と gate の判定に応じて必要な段を追加実行するモードを選ぶ。未設定時は lazy chain を使わず、chain 全体を一度に要求する。環境変数を読むのは `engine/src/program/generate.cpp` の request 処理である（`engine/src/program/generate.cpp:20161-20166,21745,22155-22180,22428-22435`）。

この設定は chain の実行量・タイミングを変える。コード上、検証ウィンドウの結果を変える設定ではなく、パイプライン復号の出力 token は直列ループと同じと説明されている（`engine/src/program/generate.cpp:21696-21703`）。

## 値と判定

環境値はリクエストごとに `std::getenv` で取得し、`std::atoi(v) != 0` で真偽に変換する。未設定は `false`。空文字や数字で始まらない文字列は `atoi` が 0 を返すため無効。整数として読まれる先頭部分が 0 なら無効、非 0 なら有効で、後続文字列は検査されない。たとえば `1`、`-1`、`2x` は有効、`0`、`0anything`、`true`、空文字は無効。先頭空白や符号は `atoi` の整数変換規則に従う。文字列全体の妥当性検査や clamp はない（`engine/src/program/generate.cpp:20163-20166`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 通常の環境変数判定 | lazy chain は OFF | `1`、`-1`、`2x` | `0`、`0anything`、`true`、空文字 |
| 有効な `STRATA_PIPELINE_SWITCH` の `lazy=` 指定 | ファイルに指定がなければ環境値を維持 | `lazy=1`、`lazy=-1`、`lazy=2x` | `lazy=0`、`lazy=true`、`lazy=` |

`STRATA_PIPELINE_SWITCH` は `STRATA_PIPELINE_DEBUG` が有効な場合に限り認識される診断用上書きである。helper は `STRATA_PIPELINE_DEBUG` が未設定、空文字、または先頭文字が `0` の場合に無効、それ以外の設定値で有効とし、その結果を static cache する。`lazy=` がファイルにあれば、その値が当該リクエストの環境値判定を置き換える。ファイルの `lazy=` も `atoi(...) != 0` で判定される（`engine/src/program/generate.cpp:679-685,20178-20195`）。

## 有効になる条件

- パイプライン自体が有効であること。通常は `--serve` のレイヤー分割で、各 stage が別 GPU にあり、MTP drafter と `--spec >= 2` が使える構成が必要。`--pipeline-windows 2` を CLI で指定できる。自動設定は HIP の対応構成などに限られ、`STRATA_PIPELINE_AUTO=0` で無効化できる。適用不可の指定は `--pipeline-windows` の検証で無効化され、理由が stderr に出る（`engine/src/program/generate.cpp:1143-1148,4114,6532-6554,6556-6573`）。
- 対象の復号ループには `pipe && pl_pw >= 2 && pl_snap_ok` が必要であり、さらに request が cancel 済みでなく、生成上限に達していないことが必要（`engine/src/program/generate.cpp:13184-13189,20142,21704-21716`）。
- その request が repetition penalty (`penalty_last_n`) を使う場合、または coupled draft sampling の場合、コードはパイプライン復号を直列実行に切り替える。このとき lazy chain の値は復号動作に使われない（`engine/src/program/generate.cpp:21705-21713`）。
- `STRATA_PIPELINE_SWITCH` がデバッグ有効状態で開けるファイルを指し、その内容に `lazy=` があれば、環境値にかかわらずその request の値を上書きする。`STRATA_PIPELINE_DEBUG` は helper 内で初回評価された状態を保存する（`engine/src/program/generate.cpp:682-685,20178-20195`）。
- `--spec-min-p` と request ごとの `spec_min_p` は lazy chain がどこまで伸びるかの判定に使われる。これらは `STRATA_PIPELINE_LAZY_CHAIN` を有効化する条件ではない（`engine/src/program/generate.cpp:18817,22155-22180`）。

## 実行時の詳細

環境変数の値は `serve` の request 処理で `pl_lazy` を初期化するたびに読み取られる。環境値そのものを保持する static cache はないため、後続 request では変更後の値が読み取られる。設定変更が既存 request の途中に反映されることはなく、その request ではローカル値 `lazy` にコピーされる（`engine/src/program/generate.cpp:20162-20166,20178-20195,21744-21746`）。

`lazy` が false の場合、chain の次ウィンドウ B のサイズが確定するまで、chain 完了または既定の drafter 段数・`spec_min_p` による終了を待つ。true の場合は、chain 出力を使って gate を評価し、window の上限や `spec_min_p` に達しておらず、gate を通る可能性があるとき、出力がそろうごとに `mtp.chain_extend(chain_n + 1, err)` で次の段を要求する。lookup 由来の A では bonus が chain の予測ではないため追加出力を要求しない。chain launch 時も lazy では初期要求数を `max(1, S_mtp - 1)` とし、非 lazy では `kVerifyNarrowT - 1` を要求する（`engine/src/program/generate.cpp:22155-22180,22428-22435`; `engine/include/strata/core/mtp.hpp:208-218`）。

遅延 chain の拡張が失敗した場合は `die(err)` に進み、パイプラインのエラー処理が処理中の GPU wait / adaptive thread を片付けて `ERR ...` を stdout に出し、終了コード 1 を返す（`engine/src/program/generate.cpp:21808-21822,22176-22178`）。

## ログと測定値

`STRATA_PIPELINE_DEBUG` が未設定・空文字でなく、先頭文字が `0` でないとき、`STRATA_PIPELINE_SWITCH` ファイルを開ければ stderr に `strata pipeline switch: ... lazy=<0|1> ...` を出し、上書き後の判定値を確認できる。switch のパスは static に保持され、ファイル内容は request ごとに読み直される。環境変数だけを指定した場合に lazy 値を明示する専用ログはない（`engine/src/program/generate.cpp:682-685,20178-20195`）。

復号 timing が有効なとき、stderr の `strata pipeline: ... outputs each (lazy)` の `(lazy)` 表記で実行モードを確認できる。ここでの値は `STRATA_PIPELINE_LAZY_CHAIN` の直接の測定ログではなく、実際に復号ループへ渡された mode の表示である（`engine/src/program/generate.cpp:22478-22488`）。対象変数について条件つきの性能測定値は確認できなかった。

## 根拠

- `engine/src/program/generate.cpp:679-685` — `STRATA_PIPELINE_DEBUG` を使う診断 helper の判定と cache。
- `engine/src/program/generate.cpp:20161-20166` — 対象環境変数の唯一の Strata 実行時読み取りと変換（`terminal/data/settings-register.json` にも設定名の登録がある）。
- `engine/src/program/generate.cpp:20178-20195` — debug switch ファイルによる request ごとの上書きとログ。
- `engine/src/program/generate.cpp:13184-13189,21704-21716` — pipeline/decode の適用条件と serial fallback。
- `engine/src/program/generate.cpp:22155-22180,22428-22435`、`engine/include/strata/core/mtp.hpp:208-218` — eager/lazy の chain 要求・延長。
- `engine/src/program/generate.cpp:22478-22488` — timing 表示。
