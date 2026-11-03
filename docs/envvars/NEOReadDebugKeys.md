# `NEOReadDebugKeys`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

この名前を SYCL engine 自身が読んで分岐するコードはありません。Intel Arc 用 setup が特定の Alchemist 構成で設定値 `1` を run config の `env` に書き、server と `sycl/serve/strata-sycl.sh` が環境変数として実行コンテナに渡します。Strata がこの値を転送した先で外部コンポーネントがどう解釈するかは、この文書の対象外です。

## 値と判定

| 経路 | 未設定 | 空文字 / `0` | その他の設定値 |
|---|---|---|---|
| Intel Arc setup が生成する config | Alchemist 条件を満たす場合は `"1"` を設定。それ以外では setup はこのキーを追加しない | setup が生成する値ではない | setup が生成する値ではない |
| `strata-sycl.sh` のコンテナ転送 | `compgen -e` に現れないため転送しない | `0` または空文字は `docker run -e` の対象から除外 | 文字列をそのまま `docker run -e NAME=value` に渡す。数値変換や真偽値 parse はしない |

setup は `to_sycl()` 内で新しい `env` 辞書を作り、Alchemist 条件では `NEOReadDebugKeys: "1"` を他の2キーとともに設定します。元 config の `env` は `out` を作る際に除外されるため、setup による再生成では元 config の同名値は引き継がれません。設定される場合は setup が `1` に固定します。手編集した config の `env` は server が親環境を複製した後に上書きで適用するので、server 起動時の同名環境変数より config の値が優先されます。`strata-sycl.sh` は設定値を文字列として検査し、`0` と空文字だけを除外します（たとえば `false` や `00` は除外されません）。

## 有効になる条件

setup がキーを自動設定するのは、選択された GPU が Alchemist と判定されたときです。判定は `driver == "i915"` または device ID が `ALCHEMIST_IDS`（`56a0`, `56a1`, `56a2`, `56a5`, `56a6`, `5690`）に含まれることです。したがって i915 では device ID によらず設定し、xe では上記 ID のときに設定します。Battlemage の device ID はこの集合に含まれず、自動設定されません。

この自動設定は Intel Arc の SYCL setup / run config 経路に限られます。`strata-sycl.sh` の転送フィルターは `NEOReadDebugKeys` を名前で許可し、手動設定された値も転送できます。別 backend の engine がこのキーを読む・転送する処理は見つかりませんでした。

## 実行時の詳細

- setup は config の `env` に値を入れてファイルへ保存します。setup が作った run script から server が起動し、`serve/server.py` の `child_env()` は `os.environ` を複製してから config の `env` の各キーを適用します。その環境で engine wrapper を起動します。
- `strata-sycl.sh` は環境名一覧を走査し、`NEOReadDebugKeys` に一致した名前の現在値を動的参照で取得します。値が空または完全一致で `0` なら転送配列に含めず、それ以外なら値を保ったまま Docker の `-e` 引数に追加します。
- shell wrapper は起動ごとに環境を読みます。setup が `1` を config に書く処理は config 生成時です。server 起動中に親環境を書き換えても既に起動した子プロセスの環境は変わりません。
- Strata 側にこのキー専用のログ、警告、終了・失敗分岐はありません。コンテナ起動や先の外部コンポーネントの結果について、Strata ソースからこのキー固有の挙動は確認できません。

## 根拠

- `sycl/setup_intel.py:45-57` — Alchemist device ID の一覧。
- `sycl/setup_intel.py:277-297,344-345,369-386` — SYCL config 変換、Alchemist 条件、生成する `env` と値。
- `sycl/setup_intel.py:477-491,520-534` — 選択 GPU を使った config 変換とファイル保存。
- `serve/server.py:4054-4068,1151-1154` — 親環境への config `env` 適用と engine 起動時の環境引き渡し。
- `sycl/serve/strata-sycl.sh:33-42,46-52` — 環境名の列挙、動的な値取得、空文字 / `0` の除外、コンテナ起動。
