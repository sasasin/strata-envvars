# `STRATA_WINDOW_WARM`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`STRATA_WINDOW_WARM=0` は engine 起動時に行う speculative verify window の事前 warm-up を止める研究用スイッチです。未設定時は warm-up を試みます。warm-up は最初の request を読む前に、policy が選択し得る window 幅ごとに token ID `1` のダミー window を実行し、初回使用時に発生する graph capture（CUDA/HIP）や初回実行（Metal）を前倒しします。通常の request の token、checkpoint、会話履歴、乱数、policy の学習統計には反映されず、expert cache がダミー token の route に応じて page-in する可能性だけが残ります（`src/program/generate.cpp:15163-15168`）。

## 値と判定

`std::getenv` の結果を関数内 `static const bool` に一度保存し、値が存在し、かつ先頭文字が `'0'` のときだけ warm-up を無効化します。文字列全体の比較や数値変換はしません（`src/program/generate.cpp:15169-15171`）。

| 条件 | unset | warm-up を無効化する値 | warm-up を止めない値 |
|---|---|---|---|
| 全 build/backend 共通 | 有効（無効化フラグは `false`） | `0`, `0anything` | 空文字、`1`, `true`, `false`, ` 0`, `00` 以外の `0` 始まり文字列ではない値。`00` も先頭が `0` なので無効化 |

大文字小文字・空白・数値としての妥当性は検査しません。したがって `false` や空文字は warm-up を無効化せず、先頭に空白がある ` 0` も無効化しません。`0` の後ろに文字があっても先頭文字のみで判定するため無効化します（`src/program/generate.cpp:15170`）。

## 有効になる条件

- `STRATA_WINDOW_WARM` が unset または先頭文字が `0` 以外であること。先頭文字 `0` の場合は warm-up block 全体を飛ばします（`src/program/generate.cpp:15170-15171`）。
- `o.spec >= 2`、`n_stages == 1`、`o.batch <= 0` が必要です。したがって speculative window を使わない設定、複数 stage の layer split、正の batch/slot 数では実行しません（`src/program/generate.cpp:15171`）。`--spec` は `o.spec` に、`--batch` と同義の `--slots` は `o.batch` に読み込まれます（`src/program/generate.cpp:3856-3858`）。
- warm-up 対象幅は `1..o.spec` のうち `lookup_size_mask(o)` に含まれる幅です。`--lookup-max-t` などにより mask から外れる幅は実行しません（`src/program/generate.cpp:1462-1480,15176-15178`）。
- backend 固有の環境変数条件はありません。Metal の `Verifier::prepare` は capture を行わず成功を返すため、その後の `run` が初回実行になります。非 Metal の prepare は既存 capture がなければ capture を試みます（`src/core/verify.cpp:4594-4610`）。

## 実行時の詳細

読み取りは engine の初期化中、warm-up 判定 block に入った際の最初の一度だけです。値は `static` に保存されるため、同じプロセス内で環境を変更しても再評価されません。CLI 引数による値の上書きはありません。CLI の speculative/batch/window-size 設定は warm-up の適用条件と対象幅を決めます（`src/program/generate.cpp:1462-1480,15169-15178`）。

有効条件を満たすと、`wtok` の各要素を `1` にしたダミー入力を作り、選択対象の各幅 `t` について `ver.prepare(t, ...)`、続いて `ver.run(t, ..., pos0=0, ...)` を呼びます。prepare が VRAM 不足を示した幅はスキップし、別の prepare failure または `run` / drive failure ではその後の幅を中断します（`src/program/generate.cpp:15172-15189`; prepare の VRAM 判定は `src/core/verify.cpp:4601-4609`）。

完了・中断いずれの場合も session を `session_zero` で初期状態に戻し、main stream を同期して drive の診断カウンターをクリアします。その後 `READY` を出して通常の request loop に進み、warm-up failure 自体はこの箇所で engine 終了条件にされません（`src/program/generate.cpp:15190-15203`）。

## ログと測定値

warm-up 条件を満たした場合、stderr に `strata serve: window warm-up: ms per width ...` を出します。各幅の所要時間、合計時間が含まれ、prepare/run failure があれば `; a window failed: ` と `werr` が続きます。VRAM 不足で幅を skip しても、その事実を示す専用文言はこのログに追加されません。条件不成立または変数で無効化された場合、この warm-up ログは出ません（`src/program/generate.cpp:15176-15198`）。

コードコメントには初回 window 幅の準備時間を初回 request に負わせない意図と、M5 Max / IQ3_S での過去の観測値が記載されていますが、測定条件を十分特定した資料ではないため、一般的な性能値としては扱いません（`src/program/generate.cpp:15163-15168`）。`docs/DETAILS.md` にこの変数の記載はありません。

## 根拠

- `src/program/generate.cpp:15163-15171` — warm-up の目的、副作用の説明、環境変数の読み取りと実行条件。
- `src/program/generate.cpp:1462-1480,15172-15198` — 対象幅、prepare/run の順序、failure 処理、ログ。
- `src/core/verify.cpp:3241-3298,4594-4610` — verifier の run/prepare と backend 差、VRAM capture failure の扱い。
- `src/program/generate.cpp:3856-3858,15190-15203` — CLI option の格納、session reset 後の READY 出力。
