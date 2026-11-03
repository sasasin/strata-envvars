# `STRATA_DRAFT_KEEP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`--draft auto` で DFlash2 と MTP を切り替えて使うサーバー経路において、現在のリクエストで使っていない側の drafter を、確定した decode window の内容で非同期に追いつかせる処理を止める診断用スイッチです。通常は `STRATA_DRAFT_KEEP` が未設定なら追いつかせる処理を行い、環境変数を設定して `atoi` の結果が 0 になるとその処理を省略します。変数は drafter の選択そのものや、現在のリクエストの draft window を決めません。

## 値と判定

コードは `std::getenv()` で取得した文字列を `std::atoi()` に渡し、その結果が 0 かで判定します。文字列全体の妥当性検査はありません。

| 環境値 | `draft_keep_off` | 判定 |
|---|---:|---|
| 未設定 | `false` | idle drafter の upkeep を許可 |
| 空文字 | `true` | `atoi("")` が 0 のため upkeep を省略 |
| `0`、`-0`、`0tail` | `true` | 変換結果が 0 のため upkeep を省略 |
| `1`、`-1`、`12tail` | `false` | 変換結果が非 0 のため upkeep を許可 |
| 数字で始まらない文字列（例: `true`, `junk`） | `true` | `atoi` の変換結果が 0 のため upkeep を省略 |

`atoi` は先頭の空白と符号を許し、先頭の十進数字列を変換します。したがって ` 1x` は非 0、`0.5` は 0 と判定されます。値域の検証や clamp はありません。読み取り式では未設定時だけ明示的に `false` とし、設定時の変換結果が 0 なら `draft_keep_off=true` です（`src/program/generate.cpp:13404-13407`）。

## 有効になる条件

値が upkeep を止めるのは、次の条件を満たすときです。

- `STRATA_HAVE_DFLASH2` が有効な build である。upkeep の分岐はこの compile-time guard の内側にあります。
- DFlash2 が実際に利用可能な状態で `use_df2` が真であり、`--draft auto` が指定されている。
- decode window が merged window ではない。

この条件下では、その request が使わない drafter の追いつき処理を省略します。現在の request が MTP を使う場合は DFlash2 の `context_async()`、DFlash2 を使い MTP もロード済みの場合は `mtp.prefill()` が通常の upkeep です。`--draft auto` の request ごとの drafter 選択は request の `draft` 指定または `--draft-rule` によって決まり、この環境変数はその選択より後の upkeep 分岐だけに作用します（`src/program/generate.cpp:15190-15235,18535-18549`）。

## 実行時の詳細

環境変数の判定は `static const bool` の初期化時に一度だけ行われ、同じプロセス内では結果が保持されます。したがって、初回評価後にプロセス環境を書き換えても再判定されません（`src/program/generate.cpp:13404-13407`）。CLI 引数や他の環境変数でこの値を上書きする処理は見つかりません。

upkeep を許可した場合、idle drafter の処理はその drafter 自身の stream にキューされ、decode window の処理と重なります。`keep_pending` が立つと次の window に進む前に `keep_sync()` が待ち、request の終了時にも同じ待機をします。環境変数によって upkeep を省略した場合は、これらの upkeep 処理と対応する待機が発生しません（`src/program/generate.cpp:17421-17430,18283-18288,18537-18549,18664-18665`）。コード上の目的は、後続の request が利用できるよう idle drafter の context / K/V を確定 window に追いつかせることです。省略時に後続 request がどう再構築・回復するかを、この分岐だけからは断定できません。

この変数専用のログ、警告、終了経路はありません。upkeep を有効にしたとき、非同期 DFlash2 context 更新の投入失敗は `ERR <err>` を stdout に出して request loop を終了し、同期時の失敗も `keep_sync()` の偽を受けて `ERR <err>` を出し終了します。MTP stream の同期失敗時には `err` が `the MTP upkeep failed` に設定されます。upkeep を省略すると、その upkeep 自体に起因するこれらの経路は通りません（`src/program/generate.cpp:17423-17430,18541-18546,18287,18664`）。

## 根拠

- 候補名の全参照検索では、実際の環境読み取りは `src/program/generate.cpp:13405` の 1 箇所です。値の利用箇所は `src/program/generate.cpp:18538` で、同名の別実装、helper 経由の読み取り、動的な名前の受け渡しは確認されませんでした。
- `src/program/generate.cpp:13404-13407` — `getenv` / `atoi` による判定と static cache。
- `src/program/generate.cpp:15190-15235` — `--draft auto` の request 単位の drafter 選択。
- `src/program/generate.cpp:17421-17430,18283-18288,18664-18665` — upkeep 同期の条件とエラー返却。
- `src/program/generate.cpp:18535-18549` — `STRATA_HAVE_DFLASH2` 下の upkeep と `STRATA_DRAFT_KEEP` による抑止。
- `docs/DETAILS.md` には DFlash2 や draft の説明がありますが、`STRATA_DRAFT_KEEP` の参照はなく、この診断用スイッチについて追加の挙動や測定値は確認できませんでした。
