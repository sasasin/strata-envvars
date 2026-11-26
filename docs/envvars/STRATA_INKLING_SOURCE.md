# `STRATA_INKLING_SOURCE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Inkling-2-Mini の不足ファイルを setup がダウンロードするとき、ファイル名を付け足す HTTP(S) のベース URL を追加する。`.strata` と tokenizer 関連ファイルでは同梱 `inkling-sources.json` より前に試され、Unsloth GGUF では `STRATA_INKLING_GGUF_SOURCE` より後、同梱 GGUF source より前に試される。GGUF の DSpark drafter (`mtp.safetensors`) では `STRATA_INKLING_DRAFTER_SOURCE` より後、固定の Thinking Machines source より前に試される。したがって GGUF 専用または drafter 専用の環境変数が有効なら、それらがこの変数より先に試行される。`terminal/setup.py` は `sources_for(name)` を呼び、設定辞書を渡していないため、この実行経路で設定ファイルの `inkling_source` は優先順位に入らない（family helper 自体は `cfg` を受け取れる）。【`terminal/strata_control/inkling_family.py:184-244`; `terminal/setup.py:10615-10625`】

この変数は setup の Inkling-2-Mini ファイル取得元を制御する。エンジンの実行時推論設定を変えるものではない。対象ファイルがすでにある場合や、ユーザー指定のローカルファイルを使う経路では取得元選択が行われない。【`terminal/setup.py:10615-10625`; `terminal/setup.py:10803-10807,10864-10872`】

## 値と判定

family helper は `os.environ`（または内部テスト・呼び出し側から渡された env 辞書）の `STRATA_INKLING_SOURCE` を `.get` で読み、真値の場合だけ値を source 候補に追加する。通常のプロセス環境では文字列全体を `_normalise` に渡し、文字列が大文字小文字を区別して `http://` または `https://` で始まる場合に限り受理する。末尾の `/` はすべて除去される。空文字は未設定と同様に扱われる。空白の trim、URL の妥当性検証、真偽値や数値への変換はない。【`terminal/strata_control/inkling_family.py:189-202,247-259`】

| 条件 | unset / 空文字 | 受理例 | 無効例 |
|---|---|---|---|
| 通常の setup 環境 | 変数が未設定、または `""` ならこの変数の候補を追加しない。同梱 source（その JSON が読める場合）へ進む | `https://mirror.example/inkling/`（末尾 `/` を除去して利用）、`http://127.0.0.1:19999/mirror` | `0`、`1`、`true`、`false`、`HTTP://host/path`、先頭に空白のある ` https://host/path`。いずれも文字列が許可 prefix で始まらず、候補に追加されない |

受理された値は `base` として保存され、ファイル名を `/` で連結した URL が作られる。`files` 指定は環境変数文字列では構成できない。URL への接続、ダウンロード、ファイル検証が失敗したときは次の source が試される。【`terminal/strata_control/inkling_family.py:247-269`; `terminal/setup.py:10627-10642`】

## 有効になる条件

- Inkling-2-Mini setup が必要ファイルを取得する経路であること。既存ファイルは `inkling_have` が見つけると取得元選択を省く。【`terminal/setup.py:10615-10620`】
- `--gguf-dir` などユーザー所有のファイル経路で対象ファイルが欠けている場合、この変数で取得せず、setup がローカル配置を案内して終了する。ローカルモデルを採用する分岐では `inkling_fetch` を通らない。【`terminal/setup.py:10621-10625,10803-10807,10852-10867`】
- `.strata` / tokenizer ファイルではこの変数が同梱 `sources` より先に試される。GGUF では `STRATA_INKLING_GGUF_SOURCE` が先、drafter では `STRATA_INKLING_DRAFTER_SOURCE` が先に追加される。各候補は後続の既定 source より優先して試される。【`terminal/strata_control/inkling_family.py:189-235`】
- OS、GPU backend、ビルド macro の条件分岐は、この変数の読み取りと source 選択にはない。これは terminal setup のファイル取得設定である。【`terminal/strata_control/inkling_family.py:189-244`; `terminal/setup.py:10615-10633`】

## 実行時の詳細

`inkling_fetch` は、ファイルがまだ取得済みでなく、`own`（ユーザー所有のローカルファイルを使う経路）でもない場合に `sources_for(name)` を呼ぶ。名前が `DRAFTER_FILES` に含まれれば drafter source、`.gguf` または既知 GGUF 名なら GGUF sources、それ以外は標準 sources に振り分けられる。【`terminal/setup.py:10615-10625`; `terminal/strata_control/inkling_family.py:238-244`】

環境変数は family module の import 時に値をキャッシュせず、各 `sources` / `gguf_sources` / `drafter_sources` 呼び出し時に `os.environ` を参照する。setup は各不足ファイルについて `inkling_fetch` を呼ぶため、その取得時点の環境値が使われる。setup 実行中に環境が変更された場合も後続の呼び出しには反映され得るが、ダウンロード開始済みの候補 URL はその取得処理中に再読込されない。【`terminal/strata_control/inkling_family.py:189-196,205-214,227-235`; `terminal/setup.py:10623-10633,10864-10872`】

受理された候補が失敗すると、setup は `"{name}: that source did not work; trying the next one"` を警告し、残りの source を順に試す。候補が空なら `"no download source for {name} is configured"` と案内を出して exit code 1 で終了する。候補を試し尽くした場合は最後の取得失敗を再送出する。【`terminal/setup.py:10625-10642`; `terminal/setup.py:1044-1056`】

## 根拠

- 候補名定数、標準/GGUF/drafter の優先順位と値の正規化: `terminal/strata_control/inkling_family.py:184-259`
- URL 組み立て: `terminal/strata_control/inkling_family.py:262-269`
- setup からの読み取り・source 試行・失敗時の警告と終了: `terminal/setup.py:10615-10642`
- 不足ファイル取得ループとローカルファイル分岐: `terminal/setup.py:10803-10807,10864-10872`
- warning / failure の表示と exit code: `terminal/setup.py:1039-1056`
