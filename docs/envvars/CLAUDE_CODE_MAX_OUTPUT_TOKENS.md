# `CLAUDE_CODE_MAX_OUTPUT_TOKENS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の `strata connect claude-code` が、Claude Code 用設定ファイル `~/.claude/settings.json` の `env` オブジェクトに出力する環境設定名である。値は対象サーバーの context に応じた出力上限として生成される。`strata connect` はこの値を設定ファイル案と `Environment:` 表示に載せるが、Strata のサーバーや CLI がこの名前を実行プロセスの環境から読み取って推論上限を変更する実装は確認できない。`claude_env` は値を `str(t.output_cap)` として作り、`claude_file` が同じ辞書を JSON の `env` に入れる（`terminal/strata_cli/launch/harness.py:45-51,158-167,343-348`）。

## 値と判定

Strata 自身は環境値を parse しない。新しい設定案で生成する値は `max(4096, context // 8)` の十進表記文字列である。context は `--context` が指定されればそれを使い、なければ実行中の launch または preset から取り、最後は `32768` を使う（`terminal/strata_cli/launch/harness.py:45-51,339-340`; `terminal/strata_cli/launch/cmd.py:1074-1080,703-725`）。たとえば context `32768` では `4096`、`40960` では `5120`、`65536` では `8192`、`131072` では `16384` を出力する。`--context` の値は数値または `k` / `m` 付きのサイズとして parse され、最低 `1024` token 未満は拒否される（`terminal/strata_cli/launch/cmd.py:46-50,173`; `terminal/strata_cli/launch/settings.py:71-81`）。

| 条件 | 未設定 | 生成される値 | 既存設定の値 |
| --- | --- | --- | --- |
| `strata connect claude-code` の表示・新規設定 | OS 環境変数の未設定状態は Strata では参照しない | JSON の `env` に context 由来の十進文字列を出力 | 表示だけでは設定ファイルを読み戻さない |
| `strata connect claude-code --write` で既存 JSON を merge | `env` にキーが無い、値が JSON `null`、または `env` がオブジェクトでない場合は生成値を使用 | 生成値を merge | 既存の非 `null` 値は、`str(value) == "4096"` の場合を除いてそのまま保持する。空文字、任意文字列、数値、真偽値も検証・変換せず保持する |

Strata が保持判定で比較するのは既存値の `str(...)` と文字列 `"4096"` の完全一致であり、大小文字、空白、数値形式の妥当性を検査しない。`"4096"` または数値 `4096` は生成値で置き換わる。`"4096x"`、`" 4096"`、`"0"`、`""`、その他の非 `null` 値は保持される（`terminal/strata_cli/launch/harness.py:402-420`）。ここでの未設定・空文字の扱いは既存 JSON の merge に限る規則で、実行時の OS 環境変数の parse 規則ではない。

## 有効になる条件

- この設定を出力するのは `claude-code` harness である。`strata connect` は対象を名前で解決し、その harness の renderer を実行する（`terminal/strata_cli/launch/harness.py:286-295,318-323`; `terminal/strata_cli/launch/cmd.py:1052-1080`）。
- 値の生成には Strata server の context が必要である。明示した `--context` が最優先で、次に選択した launch / preset の context、なければ `32768` が使われる（`terminal/strata_cli/launch/cmd.py:1074-1080`; `terminal/strata_cli/launch/harness.py:339-340`）。
- `--write` なしではファイルに書かず、案を表示する。`--write` は通常確認を求め、`--yes` で確認を省略できる。非対話入力で `--yes` がなければ終了コード `2` で書き込みを断る（`terminal/strata_cli/launch/cmd.py:1019-1038,1123-1140,1156-1167`）。
- Strata ソース内に、OS、GPU backend、build macro、server mode、model 状態でこの設定値の適用を切り替える処理はない。設定を受け取った Claude Code 側の解釈・実際の出力制限は本調査の対象外であり、Strata の挙動としては断定しない。

## 実行時の詳細

`run_connect` は引数・launch 情報から `Target` を作り、`render` で `claude_env` と `claude_file` を呼び出す。この時点で環境から `CLAUDE_CODE_MAX_OUTPUT_TOKENS` を読み取ることはない。標準出力には設定ファイル内容と環境設定の一覧を出す。`--write` の場合は `~/.claude/settings.json` を JSON merge し、新しい Strata 管理キーを設定する（`terminal/strata_cli/launch/cmd.py:1074-1080,1123-1140,1156-1167`; `terminal/strata_cli/launch/harness.py:158-167,343-348,355-369`）。

既存設定では、`_keep_output_cap` が既存の `env.CLAUDE_CODE_MAX_OUTPUT_TOKENS` を調べる。非 `null` かつ文字列化した値が `"4096"` と異なるとき、その値を merge 後の設定に戻して保持する。`"4096"` は旧 Strata の生成既定値とみなされ、新しい context から計算した値に更新される。これはファイル書き換え時だけの処理で、プロセス内 cache や起動後の再評価はない（`terminal/strata_cli/launch/harness.py:364-369,402-420`）。

JSON の読み込み・書き込みで `OSError` が起きると、そのファイルを `failed` として報告し、以後のファイルがあれば `not_written` とする。通常出力では `Could not write <path>: <reason>.` を表示して終了コード `1` を返す。JSON 出力ではエラー情報を含む結果を返して同じコードで終了する（`terminal/strata_cli/launch/cmd.py:1039-1050,1108-1115,1156-1167`）。

## ログと測定値

Strata は `Good to know:` の案内に、context と生成値を埋めた `Set CLAUDE_CODE_MAX_CONTEXT_TOKENS to the served context (%d here) and CLAUDE_CODE_MAX_OUTPUT_TOKENS=%d: ...` を表示する。書き込み成功時は `Created` または `Merged` とファイルパスを表示する（`terminal/strata_cli/launch/harness.py:234-244`; `terminal/strata_cli/launch/cmd.py:1137-1141,1158-1162`）。

ソースにこの変数の実行時効果を測定した Strata の測定値はない。上記案内は CLI が表示する説明文であり、Claude Code 側の動作を Strata が検証した結果とは扱わない。

## 根拠

- `terminal/strata_cli/launch/harness.py:45-51` — context から出力上限を計算。
- `terminal/strata_cli/launch/harness.py:158-167,286-295` — Claude Code 用 env map と settings ファイル定義。
- `terminal/strata_cli/launch/harness.py:355-369,402-420` — settings の merge と既存値の保持・更新規則。
- `terminal/strata_cli/launch/cmd.py:1019-1050,1074-1080,1123-1167` — `strata connect` の選択、表示、書き込み、失敗結果。
- `terminal/strata_cli/launch/settings.py:71-81` — `--context` のサイズ parse と下限。
