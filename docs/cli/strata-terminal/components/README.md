# `strata components`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components` とその必須サブコマンド |
| POSIX の入口 | `bin/strata` |
| 主な実装 | `strata_cli/cli.py`、`strata_cli/update_cmd.py`、`strata_control/doctor.py`、`strata_control/components.py`、`strata_control/engine_component.py` |

## 役割

インストール済みコンポーネントやローカルのエンジン package、component manifest と OS/backend の適合性を確認し、対応 backend の一覧を表示するコマンド群です。また、`components update` で署名済み feed から更新を行い、`components rollback` で直前の更新前の engine に戻せます。`components` のサブコマンドは必須です（`strata_cli/cli.py:114-140`）。

トップレベル parser の説明は「read-only installed component inventory」ですが、`update` と `rollback` は更新を行います。読取専用の確認と更新操作を区別して使ってください（`strata_cli/cli.py:114-140`、`strata_cli/update_cmd.py:1-11,163-224`）。

## 代表的な使い方

```sh
# 保存済み profile に必要なファイルを確認
strata components verify --profile my-profile

# manifest がこの環境で利用可能か確認（取得・展開はしない）
strata components plan ./component.json

# 対応 OS と backend の組み合わせを表示
strata components backends

# ローカル component folder の engine 状態を確認（取得しない）
strata components engine

# 署名済み feed の更新内容を確認するだけ
strata components update --check

# 直前に保持された engine に戻す
strata components rollback
```

`verify` は `--profile` に保存済み profile 名または run-config JSON パスを渡します。`--live` は host GPU を調べる追加確認です。`plan` は manifest パスを位置引数に取り、必要なら `--backend` / `--target` で判定対象を指定します。詳しい option は各サブコマンド文書を参照してください（`strata_cli/cli.py:116-138`）。

## サブコマンドと実行モード

| サブコマンド | 動作 | 主な副作用・終了時の注意 |
| --- | --- | --- |
| `verify` | 指定 profile/run config の engine、tokenizer、model/pack 等の必須ファイルを確認。`--live` は GPU probe を追加 | engine は起動しません。必須 component の欠落・不正や live check の問題は exit 5 になり得ます。live probe は外部 GPU 情報取得を伴います |
| `plan MANIFEST` | manifest を読み、platform/backend の互換性と artifact 情報を表示 | ダウンロード、展開、ファイル変更なし。manifest 不在・不正は error。互換性なしは `usable: false` と理由を表示します |
| `backends` | コードに定義された OS/backend matrix を表示 | 読取専用。未対応の組み合わせは試行対象外です |
| `engine` | ローカル component folder を調べ、この PC で利用できる engine と問題を表示 | ダウンロード・変更なし。engine が利用不可の場合は notice を出し exit 5 になります |
| `update` | `strata update` と同じ更新処理。署名済み feed から engine と Control を更新 | ネットワーク取得とローカル更新を行います。`--check` は feed を確認するだけです。engine は test start 成功後に切替え、前の版を rollback 用に保持します |
| `rollback` | 前回更新で保持された旧 engine に戻す | ローカルの engine を切り替えます。保存済み tuning preset は削除せず、必要に応じて短い再確認対象として印を付けます |

互換性 matrix は現行ソースで Metal/macOS arm64、CUDA と HIP/Windows・Linux x86_64、SYCL/Linux x86_64、CPU/macOS・Windows・Linux の組み合わせです。これはプロジェクトが対応を表明する組み合わせであり、実機での性能・全環境の qualification を保証するものではありません（`strata_control/targets.py:20-29,42-51`）。

## 主要な動作と注意点

- `verify` は設定から engine、tokenizer、モデル関連のパスを解決し、必須項目の欠落・不正を報告します。live probe を付けない通常の確認は外部 GPU probe を呼ばず、engine も起動しません。結果には manifest hash による完全性検証が未実施である旨が含まれます（`strata_control/doctor.py:146-160,162-235`、`docs/TERMINAL.md:158`）。
- `plan` は manifest を厳格に解析して互換性を判定します。人間向け出力または JSON を選べます。対象 platform を省略すると host platform を使います。manifest の読み込み・形式エラーはエラー経路となります（`strata_cli/cli.py:1966-2011`）。
- `engine` は既定の per-user component folder、または `--components-dir` のローカル内容を調べます。backend は既定で検出し、`--backend` で指定できます。`--full` は entrypoint だけでなく全ファイルを hash する指定です。確認経路は取得を行いません（`strata_cli/cli.py:132-138,2014-2041`）。
- `update` はコンポーネント取得を行う明示的な操作です。signed feed が必要で、engine が稼働中なら通常は拒否されます（`--wait` による待機指定もあります）。`STRATA_NO_ACQUIRE` により取得が禁止されている場合は拒否されます。更新失敗時は旧 engine を維持する設計です（`strata_cli/update_cmd.py:1-11,30-40,163-234`）。
- `rollback` は旧 engine を復帰させます。稼働中 engine を扱う場合の待機・拒否経路は update 実装を通ります（`strata_cli/update_cmd.py:185-196,237-252`）。

## 関連文書

- [CLI 索引](../../README.md) — `strata components` と各オプション文書へのリンク
- [`verify` 概要](verify/README.md)、[`plan` 概要](plan/README.md)、[`backends` 概要](backends/README.md)、[`engine` 概要](engine/README.md)
- [`update` 概要](update/README.md)、[`rollback` 概要](rollback/README.md)
- [`strata doctor` の説明](../../doctor/README.md) — installed component の read-only 診断
- Strata `docs/TERMINAL.md:158` — `doctor` / `components verify` の範囲と live probe の注意
- Strata `docs/INSTALL.md:114-116` — update と rollback の利用者向け説明

## 根拠

- Strata `strata_cli/cli.py:114-140` — `components` parser、必須サブコマンド、verify/plan/backends/engine と update/rollback の登録。
- Strata `strata_cli/cli.py:1966-2041,2129-2139` — plan/engine/backends の処理と各処理への dispatch。
- Strata `strata_cli/update_cmd.py:1-11,30-59,163-234,237-252` — update/rollback の用途、parser、実行・失敗・待機経路。
- Strata `strata_control/doctor.py:146-160,162-235` — verify の read-only component inventory と profile/live 条件。
- Strata `strata_control/components.py:52-58,136-189`、`strata_control/targets.py:20-51` — manifest schema/kind と互換 backend matrix。
- Strata `strata_control/engine_component.py:969-988` — engine 状態確認が取得を行わず、利用不可を report に返す実装。
- Strata 利用者向け資料: `docs/TERMINAL.md:158`、`docs/INSTALL.md:114-116`。
