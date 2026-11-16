# `strata launch --gpu-roles`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--gpu-roles` |
| 別名 | なし |
| 値 | `LIST`。カード番号と `main` / `helper` / `off` の組を列挙する |

## 役割

起動時に使うグラフィックスカードごとの役割を指定する。`Main` は回答の最終段階を担当し、`Helper` はモデルの一部を保持する。`Off` のカードは使わない。明示した指定にないカードも `Off` として扱われる。これはカード番号だけを選ぶ `--gpu` の代わりに使うオプションである（`strata_cli/launch/cmd.py:111-117`、`strata_control/gpu_roles.py:1-9,247-252`）。

## 使い方

2 枚のカードが番号 `0` と `1` で検出される環境で、番号 `1` を Main、番号 `0` を Helper にして計画だけ表示する例:

```sh
strata launch --plan --model iq3_xxs --gpu-roles 1=main,0=helper
```

`--plan` は実行内容を表示して終了し、変更を行わない（`strata_cli/launch/cmd.py:14-28,146`）。実際に起動する場合は `--plan` を外す。

## 値と既定値

- 各指定は `カード番号=役割` 形式で、`,` または `;` で区切れる。`1:main` のように `:` を区切りにする形式も受理される。大文字小文字は区別せず、前後の空白は除去される（`strata_control/gpu_roles.py:218-230`）。
- 役割は `main`、`helper`、`off` のいずれか。カード番号は 0 以上の数字でなければならない。同じカードを複数回指定できず、`main` は最大 1 枚まで（同: `229-238`）。
- 空要素は無視されるため、区切り文字の連続や末尾の区切りは、それ自体ではエラーにならない。空文字列 `""` は `settings_from_args` の truthy 判定で処理を素通りし、未指定と同じ扱いになる。一方、空白のみや区切り文字のみの非空文字列は parse され、「no cards named」エラーになる（`strata_cli/launch/cmd.py:256-262`、`strata_control/gpu_roles.py:221-238`）。形式不正、未知の役割、重複カード、複数の Main もエラーになる。
- Main を指定しなくても値は受理される。少なくとも 1 枚が Main または Helper なら、実行時にカード性能・メモリ等に基づいて最適な有効カードが Main に補われる。単独で有効なカードがあればそれが Main になる（同: `138-150,247-252`）。
- 引数を省略した場合の `LaunchSettings.gpu_roles` は `None` で、明示的なカード役割指定はありません（`strata_cli/launch/settings.py:81-92`）。この場合は既存設定または推奨値など別の選択経路が使われます（`strata_cli/launch/runner.py:398-429`）。
- 同じ `--gpu-roles` を複数回書いた場合、CLI parser は通常の単一値引数として登録しているため、後の値が前の値を置き換える（`strata_cli/launch/cmd.py:116-117`）。

## 実行時の動作

parser は値を文字列として受け取り、`settings_from_args` が `strata_control.gpu_roles.parse_roles` で文法を検証して `LaunchSettings.gpu_roles` にカード番号を文字列キーとする辞書として格納する。`--gpu` も同時に指定すると `ValueError` になる（`strata_cli/launch/cmd.py:251-262`）。この段階の文法検証では、番号が実機に存在するかは検査しない。

その後、launch は指定番号がこのビルドで使えるカードに存在するか確認する。存在しない番号があればカード一覧を添えた error notice を作り、計画表示・起動のどちらも終了コード `2` で拒否する。指定されたカードがすべて `off` の場合は拒否ではなく警告 notice になる（同: `441-449,836-843`）。カード一覧はエンジンの vendor に合うカードを基準にするため、別 vendor のカード番号は有効な選択肢にならない。

起動時には、検出されたカードすべてについて、指定がないカードを `off` として役割辞書を補完し、`normalize` で有効カードがある場合の Main を整える。役割辞書から Helper 群を先、Main を最後にしたカード順を作り、実行設定に `gpu_roles` と旧形式との互換用 `gpu` / `gpu_order` 等の mirror を書き込む。複数カードなら必要に応じて layer split も設定される（`strata_cli/launch/runner.py:350-365,398-410`、`strata_control/gpu_roles.py:138-150,195-214`）。launch 用設定ファイルは `launch_dir()` 内に書き込まれる（`strata_cli/launch/runner.py:1692-1714`）。

`--preset` と併用した場合は、保存済み設定に対してこのフラグの値を上書きして今回の起動に使う。再利用できる launch preset として保存するのは `--save-preset` を指定した場合である（`strata_cli/launch/cmd.py:206-211,251-262,914-918`）。

## 適用条件と副作用

- カード番号は 0 始まりの検出番号である。画面上の `GPU 1` は番号 `0` を指す（`strata_control/gpu_roles.py:64-66`）。
- 値に書かなかったカードは Off になるため、たとえば `1=main` はカード `1` だけを有効にする指定となる（同: `247-252`）。
- すべて Off の場合も parser は受理し、launch は「カードなし」の警告を出す。すべてのカードを無効にしたとき実際に起動できるかはエンジン/backend に依存し、このオプションの parser だけから一律の起動可否は確定できない（`strata_cli/launch/cmd.py:441-449`）。
- 実際の起動ではモデル取得や起動設定の作成・書き込みなど、`strata launch` 自体の処理が行われる。`--plan` では変更しない（`strata_cli/launch/cmd.py:25,146,851-877`）。

## 出力とエラー

- 不正な文法や `--gpu` との併用は `ValueError` となり、通常出力では `strata: ...` を stderr に表示して終了コード `2`。`--output json` の場合は標準出力に `ok: false` とエラー情報の JSON を返す（`strata_cli/launch/cmd.py:251-262,716-721,961-964`）。
- 実機にないカード番号も、利用可能カードの番号を示す error notice として終了コード `2` になる。全カード Off はこの時点では警告であり、同じ理由だけでは拒否されない（同: `441-449,836-843`）。
- `--plan` で有効な値を指定すると、カード役割を含む計画を表示して `Nothing was changed.` と出力し、終了コード `0` で終わる（同: `851-877`）。

## 根拠

- `strata_cli/launch/cmd.py:111-117` — `--gpu` と `--gpu-roles` の parser 登録・説明。
- `strata_cli/launch/cmd.py:251-262` — `--gpu` との排他、値の parse、設定への反映。
- `strata_control/gpu_roles.py:218-252` — 値の文法、validation、未指定カードと Main の補完。
- `strata_cli/launch/cmd.py:441-449,836-843` — 実機カードとの照合、警告・拒否。
- `strata_cli/launch/runner.py:350-365,398-410,1692-1714` — 実行設定にカード役割を適用し、launch 設定を書き込む処理。
- `strata_control/gpu_roles.py:138-150,195-214` — Main の正規化、Helper/Main の順序、互換設定への変換。
- `strata_cli/launch/cmd.py:716-721,851-877,961-964` — エラー出力、計画表示、終了コード。
