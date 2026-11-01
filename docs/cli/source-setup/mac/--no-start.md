# `--no-start`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | macOS Apple Silicon 用 source setup（`setup.sh` → `setup.py` → `metal/setup_mac.py`） |
| オプション | `--no-start` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`） |

## 役割

Mac 用セットアップを最後まで行い、設定ファイルと起動スクリプトを作成した後、モデルサーバーをその場で起動せずに終了します。モデルやエンジンの導入を省略するフラグではありません。

## 使い方

リポジトリのルートで、例えば次のように実行します。

```sh
./setup.sh --setup --model Q2_0 --yes --no-start
```

`setup.sh` は引数を `setup.py` に渡し、通常の macOS source setup は `setup.py` から `metal/setup_mac.py` に引き渡されます。そこで `--no-start` を含むオプションが解析されます（`setup.sh:6-12`, `setup.py:9068-9069`, `setup.py:7703-7707`, `metal/setup_mac.py:327-356`）。

## 値と既定値

値は不要です。指定すると真、未指定なら偽です。parser は `action="store_true"` で定義され、値の範囲検証はありません。複数回指定しても真のままです（`metal/setup_mac.py:349`）。

Mac parser は `parse_known_args()` を使い、認識しない引数をエラーにせず `not used on a Mac: ...` と警告します。そのため `--no-start` の後ろに誤って値を付けると、その値は未使用引数として警告されます（`metal/setup_mac.py:356-358`）。

## 実行時の動作

- 既存の Metal 設定が見つかった場合、通常は既存設定ですぐサーバーを起動します。`--no-start` を指定すると、この即時起動分岐の条件から外れ、Mac の確認とセットアップ経路へ進みます（`metal/setup_mac.py:369-372`）。
- 通常のセットアップ経路では、Python 依存関係の導入、Metal engine のビルド確認、モデルの取得・準備などが行われます。最後に `strata-<model>.json` と `run-<model>.sh` を書き、案内を出した後、`--no-start` が真なら `0` を返して終了します（`metal/setup_mac.py:424-434`, `metal/setup_mac.py:450-540`, `metal/setup_mac.py:542-570`）。
- このため、既存の設定がある状態で `--no-start` を付けても単なる「起動せず終了」ではなく、通常はセットアップ手順を再評価します。`--setup` はモデル選択や設定変更を明示するために併用できます。
- `--check` を併用すると Mac の問題確認後にその場で結果コードを返すため、設定作成や `--no-start` による最終分岐には進みません（`metal/setup_mac.py:373-385`）。`--update` は engine の処理後にモデルファイルを変更せず終了する独立経路です（`metal/setup_mac.py:428-448`）。

## 適用条件と副作用

この文書のスコープは Apple Silicon Mac で `STRATA_CONTROL_INSTALL` が `1` でない source setup です。macOS 上でも Control アプリのインストール経路は `setup.py` 内で処理され、`metal/setup_mac.py` へは委譲されません（`setup.py:9068-9069`, `setup.py:9220-9223`）。

`--no-start` は server 起動を抑止するだけです。セットアップ中のファイル・ネットワーク・build 副作用は残ります。成功経路では設定 JSON を一時ファイル経由で置換し、実行用 shell script を作成して実行可能にします（`metal/setup_mac.py:559-562`, `setup.py:6490-6495`, `setup.py:7647-7660`）。オプションが付いていても、セットアップ途中の失敗は回避しません。

## 出力とエラー

成功時は設定・起動スクリプトの場所と、次回の起動方法を標準出力に表示し、server プロセスを呼び出さず終了コード `0` を返します（`metal/setup_mac.py:562-570`, `setup.py:887-888`）。例えば Mac の要件確認で失敗した場合は `S.fail()` が理由と再実行案内を標準出力に表示し、終了コード `1` で終了します（`metal/setup_mac.py:373-385`, `setup.py:904-909`）。

## 根拠

- `setup.sh:6-12` — wrapper が全引数を `setup.py` に転送。
- `setup.py:9068-9069`, `setup.py:7703-7707` — 通常の macOS setup の委譲条件と呼び出し。
- `metal/setup_mac.py:327-358` — Mac parser、`--no-start` 定義、未知引数の警告。
- `metal/setup_mac.py:369-372` — 既存設定からの通常起動を抑止する条件。
- `metal/setup_mac.py:542-570` — 設定・起動スクリプト作成後の終了分岐。
- `setup.py:6490-6495`, `setup.py:7647-7660` — 設定の書き込みと起動スクリプト作成。
- `setup.py:904-909` — セットアップ失敗時の表示と終了。

調査は上記 commit のソースに限定しました。macOS 上での実機実行や Release 配布物の照合は行っていません。
