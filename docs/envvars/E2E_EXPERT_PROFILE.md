# `E2E_EXPERT_PROFILE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/context-e2e.mjs` が、実 engine を使う context E2E 実行時の expert profile ファイルの場所を選ぶために読む変数です。これは Strata engine や `serve/server.py` が直接読む環境変数ではありません。指定パス（または既定パス）が存在する場合に限り、スクリプトが server config の `args` に `--expert-profile <path>` を追加します。ファイルがなければこの引数は付かず、E2E スクリプトは profile なしで続行します。

この用途は `apps/host/scripts/context-e2e.mjs` に限られます。Strata リポジトリ内の候補名の全参照検索では、同スクリプト内の定義と利用の2箇所だけでした。

## 値と判定

スクリプトは `process.env[name] ?? fallback` という共通関数で値を選びます。Node.js の環境値が未設定（`undefined`）なら、Windows 固有の既定パス `C:\Users\AI-Server\AppData\Local\Programs\Strata\control\data\expert-profile.bin` を使います。環境値が設定されている場合は文字列をそのまま使います。空文字、空白、相対パスの正規化や内容検査はしません。

その後 `existsSync(PROFILE)` の結果だけで引数の有無を決めます。

| 状態 | 動作 |
|---|---|
| 未設定 | 上記の既定パスを検査し、存在するとき `--expert-profile` に渡す |
| 空文字 | 空文字のパスを検査する。通常のファイルパスとして存在しないため、引数を追加しない |
| 設定済みでパスが存在する | 指定された文字列を `--expert-profile` の値として追加する |
| 設定済みでパスが存在しない | 引数を追加せず、警告やエラーを出さない |

`existsSync` はファイル形式や読み取り可能性を確認しません。対象が存在していても不正な profile なら、後段の engine が拒否します。文字列の `true` / `false`、数値、大小文字、範囲といった真偽値 parse はありません。

## 有効になる条件

- E2E スクリプトが `E2E_BASE_URL` なしで起動し、自前の `serve/server.py` を立ち上げる経路でのみ、スクリプトが書いた config がその server に渡されます。`E2E_BASE_URL` が設定されていると、スクリプトは既存 server を使い、自前 server を起動しません。その場合も config ファイル自体は作られますが、そこにある `--expert-profile` は起動中の既存 server へ適用されません。
- `E2E_EXPERT_PROFILE` のパスが `existsSync` に通る必要があります。存在しないパスでは profile オプションを省きます。
- `STRATA_HARNESS_DIR` が未設定なら、profile の有無によらずスクリプトは `STRATA_HARNESS_DIR is not set` を stderr に出し、終了コード 2 で終了します。
- 生成 config には `expert_profile_save` キーがありません。server の `engine_args()` は config の `args` を基に engine 引数を構成し、`learned_profile_args()` は保存 profile の設定がなければ引数を変更しません。

## 実行時の詳細

スクリプトはモジュール評価時に `PROFILE` を決め、config 作成時にそのパスの存在を調べます。設定値をキャッシュする仕組みや実行中の再読込はありません。profile が存在する場合、config の `args` に `--expert-profile` とパスを別々の要素として書きます。通常の自前 server 経路では、生成した config を `serve/server.py --config <file>` に渡し、server は `engine_args(cfg)` の結果を `StrataEngine` に渡します。engine 側では `--expert-profile` の次の引数を profile path として保存します。

engine は profile を読み込めない場合、エラー内容を `strata generate: ...` として stderr に出し、終了コード 1 で戻ります。検査にはファイルを開けること、ヘッダー長、`STRP` magic、version 1、model の layer/expert 数との一致、rank 数が slot 数を超えないこと、ranked list が切れていないこと、各 layer/expert 番号が範囲内であることが含まれます。正常に読めると `strata generate: profile <path>: <count> ranked pairs, built for <slots> slots` を stderr に出します。engine の CLI 説明では `--expert-profile` を profile から VRAM tier を事前ロードする引数としています。これらは `E2E_EXPERT_PROFILE` 自体の処理ではなく、スクリプトが渡した CLI 引数に対する engine の処理です。

## 根拠

- 候補一覧: 調査対象文書リポジトリ `docs/envvars/000_envvers.md:350`（候補名の掲載。実装の根拠ではない）。
- 参照の全件検索: Strata リポジトリで `rg -n --hidden --glob '!.git/**' 'E2E_EXPERT_PROFILE' .` を実施し、一致は `apps/host/scripts/context-e2e.mjs:29` と `:57` のみ。
- 値の取得・既定値: `apps/host/scripts/context-e2e.mjs:25-34`。
- 未設定の Harness 変数による早期終了、profile パスの存在判定と config 引数への追加: `apps/host/scripts/context-e2e.mjs:47-60`。
- 自前 server の起動条件、親環境の継承、既存 server URL の選択: `apps/host/scripts/context-e2e.mjs:36-37,78-97`。
- config の `args` を engine 引数へ使う処理: `serve/server.py:3245-3264,9273-9280`。profile save 設定がない場合の扱いと、設定がある場合の同 model profile 優先判定: `serve/server.py:3368-3388`。
- CLI の引数説明と parse: `src/program/generate.cpp:1112-1117,3336-3339`。
- 資料との照合: `docs/DETAILS.md:85-88` は `tools/make_profile.py` と `--expert-profile` を説明していますが、`E2E_EXPERT_PROFILE` には触れていません。ここでの環境変数の用途は context E2E スクリプトの実装に基づきます。
- engine における profile の読込と失敗時の stderr・終了: `src/program/generate.cpp:5153-5159,5194-5195`。
- profile ファイル検証の条件とエラー文: `src/core/expert_cache.cpp:163-229`。
