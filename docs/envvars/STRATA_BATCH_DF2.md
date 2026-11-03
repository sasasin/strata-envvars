# `STRATA_BATCH_DF2`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`--serve` の `--batch` 各 slot に DFlash2 drafter を用意し、batch window で slot ごとの draft を行うか決めます。各 slot の drafter は solo DFlash2 と pack を共有し、独立した K/V ring と buffer を持ちます。この変数は DFlash2 自体を選択する設定ではありません。`--draft dflash2` などで solo drafter が起動していることが必要です。

## 値と判定

値全体の parse や数値変換はしません。`std::getenv` の結果と先頭文字だけを調べます。

| 環境値 | 判定 |
|---|---|
| 未設定 | 既定判定に進む。条件を満たす layer split で既定 ON、それ以外は OFF。 |
| 空文字 | 明示 ON/OFF のどちらにもならず、未設定と同じ既定判定。 |
| 先頭文字が `0`（例: `0`, `0abc`） | 明示 OFF。 |
| 非空で先頭文字が `0` 以外（例: `1`, `true`, `false`, ` 1`） | 明示 ON を要求する。文字列の妥当性、大文字小文字、後続文字は検査しない。 |

明示 ON は適用条件を無視する強制ではありません。Metal build は常に要求を OFF にし、共通の batch-MTP 条件などを満たさなければ slot draft は無効になります。実装: `src/program/generate.cpp:6470-6480`。

## 有効になる条件

この判定は `generate.cpp` の batch 構成時に一度行われます。実装上の有効条件は次のとおりです。

- `--draft dflash2` が指定され、`--draft auto` ではない。
- `--batch` が 2 以上で `--serve` を使い、同じ GPU に分割した layer split（`split_same`）ではない。
- Metal build ではない。さらに slot-drafter の実装は `STRATA_HAVE_DFLASH2` の build guard 内にある。
- `--spec` が 2 以上である。layer split では各 stage が別 GPU にあること。
- 複数 group の layer split では pipeline 側の slot は draft しません。共通 batch-MTP gate は `groups > 1` かつ `mtp_piped` でない構成を OFF にします。`STRATA_PIPED_MTP` によって gate が通る場合も、DFlash2 slot draft が pipeline group で実行されることを意味しません（`src/program/generate.cpp:6468-6469,6490-6498`）。
- layer split で helper expert cache (`remote_caches`) を使う構成では使えない。

未設定または空文字の場合の既定 ON は、`stages` が空でなく、`batch_groups_for(false).groups <= 1` の layer split に限られます。従って通常の単一 GPU は既定 OFF で、非空の `STRATA_BATCH_DF2` 値（先頭が `0` 以外）で要求できます。明示 `0` は既定 ON の経路も OFF にします。

この要求が立つと `batch_mtp` も有効になります。そのため `--batch-mtp` または `STRATA_BATCH_MTP` は slot DFlash2 を使う必須条件ではありません。ただし共通 gate が警告を出す条件（batch/spec 不足、適切な layer split でない、serve でない、group 構成不適合、helper cache など）では `batch_mtp` が OFF になり、slot drafter は作られません。関連実装: `src/program/generate.cpp:6482-6506`。

この変数だけでは solo DFlash2 は起動しません。DFlash2 側には native pack、`--draft-model`、対応する build、通常の DFlash2 起動条件が必要です。起動できない場合、fallback MTP があれば slot DFlash2 は OFF になり、fallback なしなら DFlash2 の起動失敗で serve の開始が終了します。根拠: `src/program/generate.cpp:6765-6818`。

## 実行時の詳細

`batch_df2_wanted` は batch 初期化の位置で `const bool` として一度評価され、以降 `STRATA_BATCH_DF2` を読み直しません。実行中に環境値を変更しても判定は変わりません。子プロセスへの転送処理はこの設定箇所にはありません。値は slot drafter の割当条件として使われ、`--draft dflash2` や `--batch` などの CLI 設定より優先してそれらを置き換えるものではありません。読み取りと gate: `src/program/generate.cpp:6470-6506`。

要求と共通 gate を通過し、solo DFlash2 が動作中なら、Strata は batch slot ごとに drafter を clone allocate します。割り当て時に失敗すると slot 番号とエラーを stderr に出し、`return 1` します。solo drafter が起動しなかった場合は `WARNING: STRATA_BATCH_DF2 is off: DFlash2 is not running` を出し、slot DFlash2 と batch-MTP を OFF にします。根拠: `src/program/generate.cpp:6820-6840`。

serve 初期化では slot drafter を solo drafter に bind し、最大 draft 数を設定して graph を prepare します。bind / prepare の失敗は `strata serve: STRATA_BATCH_DF2: slot ...` を stderr に出して `return 1`。成功時は `... slot drafters ready ...` を stderr に出します。fallback のため solo drafter が動作しなかった場合は `STRATA_BATCH_DF2 is off: DFlash2 did not start` を出して slot DFlash2 を無効化します。根拠: `src/program/generate.cpp:11185-11196`。

slot admission 時には solo drafter の K/V state を slot drafter にコピーし、各 slot の最初の draft を作ります（`src/program/generate.cpp:13730-13735,18938-18950`）。batch window 後は slot が有効なら、その window の committed rows の taps を使って次の draft を作ります。デフォルトでは spare row がない slot は drafter を動かさず taps を保留し、spare row が戻った時に catch-up します。`STRATA_BATCH_DF2_DEFER=0` はこの保留をせず毎 round draft する別設定です。draft/catch-up の失敗は `ERR batch DFlash2 slot ...` を stdout に出し、batch 処理を失敗させます。根拠: `src/program/generate.cpp:14085-14147`。

batch の集計出力では、defer した row 数と catch-up の回数・row 数・時間を `strata batch: DFlash2 slots: ...` として stderr に出します（`src/program/generate.cpp:14205-14212`）。

## 根拠

- 全参照を `rg -n --hidden --no-ignore --glob '!.git/**' --fixed-strings 'STRATA_BATCH_DF2'` で確認。環境から値を読む箇所は `src/program/generate.cpp:6471` の一箇所で、共通 env helper や動的な名前渡しによる追加読み取りは見つかりませんでした。
- 値判定・既定値・backend 条件: `src/program/generate.cpp:6470-6480`。
- batch-MTP gate と条件別警告: `src/program/generate.cpp:6482-6506`。
- DFlash2 build guard、solo drafter の起動条件、fallback: `src/program/generate.cpp:6684-6692,6765-6818`。
- slot drafter の割当、bind、prepare と起動ログ: `src/program/generate.cpp:6820-6840,11185-11196`。
- slot state の引継ぎ・draft 実行・失敗観測: `src/program/generate.cpp:13730-13735,14085-14147,18938-18950`。
