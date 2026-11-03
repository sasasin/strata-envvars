# `GPU_ROLES`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`GPU_ROLES` は Strata Docker イメージの entrypoint が読む設定で、カードごとの `main` / `helper` / `off` を `strata launch --gpu-roles LIST` に渡します。engine が直接 `GPU_ROLES` を読む箇所は見つかりませんでした。環境変数を CLI 引数へ変換するのは `docker/entrypoint.sh` です (`docker/entrypoint.sh:218-224`)。

`main` は engine のカード順の末尾、`helper` はそれより前、`off` はカード一覧から除外されます。setup は CLI の指定を run settings の `gpu_roles` として保存し、複数カードの場合は指定順を維持します (`setup.py:9758-9765,10886-10893`)。server は保存された役割から engine 用カード一覧を作り、役割が有効なら速度による並べ替えをしません (`serve/server.py:3298-3305,3315-3317,3831-3833`)。

## 値と判定

Docker entrypoint では `${GPU_ROLES:-}` を評価し、unset と空文字をどちらも空として扱います。値から ASCII 空白文字 ` ` をすべて削除し、空でなければ CLI 引数に追加します (`docker/entrypoint.sh:220-224`)。したがって、半角スペースだけの値は未設定と同じく引数になりません。タブ等はこの `tr` では削除されませんが、CLI 側で各項目・番号・役割の前後を trim します。値全体が空白だけなら項目が空になり、カード指定なしのエラーです (`strata_control/gpu_roles.py:221-235`)。

| 入力 | 処理 |
| --- | --- |
| `1=main,0=helper` | 指定カードに役割を割り当てる。 |
| `1:main;0:helper` | `:` と `;` も区切りとして受け付ける。 |
| `main` / 不正な役割 / 数字でないカード番号 | `--gpu-roles: ...` の CLI エラー。 |
| 同じカードの重複指定 | CLI エラー。 |
| `main` が複数 | CLI エラー。 |
| `main` の指定なし | 有効カードのうち番号が最大のカードを `main` にする (`setup.py:9755-9762`)。 |
| 名前にないカード | `off` として扱う (`strata_control/gpu_roles.py:247-252`)。 |
| 空文字、または空白を除くと空 | 引数を渡さず、役割指定なし。 |
| すべて `off` | CLI 引数は作られるが、setup は Main または Helper がないとしてエラーにする (`setup.py:9755-9757`)。 |

値を数値変換する処理はありません。役割名は小文字化されるため `MAIN` も受け付けます (`strata_control/gpu_roles.py:225-230`)。

## 有効になる条件

- 通常の Docker 起動（引数なし、または最初の引数が `run` / `serve`）で entrypoint の設定組み立てを通る場合に限って環境変数を読みます。別コマンドを指定した場合は entrypoint がコマンドを直接 `exec` し、この設定処理を通りません (`docker/entrypoint.sh:53-56`)。
- `GPU_ROLES` が空でないとき、`GPUS` が非空なら `GPU` より優先され、選ばれた GPU 指定が `all` / `ALL` 以外の場合は競合として stderr に `Set GPU_ROLES or GPU / GPUS, not both.` を出し、終了コード 2 で停止します。`GPUS` と `GPU` がどちらも空なら競合しません (`docker/entrypoint.sh:203-224`)。
- Docker entrypoint は役割を `--gpu-roles` として launch に渡します (`docker/entrypoint.sh:220-223,274-285`)。setup CLI は `--gpu` / `--gpus` と同時指定された場合もエラーにします (`setup.py:9746-9754`)。
- この環境変数を読むのは entrypoint の起動時だけです。子の `strata launch` へは値そのものではなく CLI 引数が渡されます。setup は指定役割を run settings に書き込み、server はその保存値からカード順を決めます (`setup.py:10886-10893`, `serve/server.py:3298-3305`)。

## 実行時の詳細

entrypoint は `GPU_ROLES` から通常の空白を除去した結果が非空なら、`--gpu-roles "$roles"` を追加して `have=1` にします。これにより通常の Docker launch 引数に含まれ、失敗した場合は entrypoint が `strata launch stopped with code ...` を stderr に出してコンテナを終了します (`docker/entrypoint.sh:220-224,274-291`)。

setup の役割引数パーサーはカンマまたはセミコロンで項目を分け、`number=role` または `number:role` を読みます。カード番号は数字のみ、役割は `main` / `helper` / `off` です。項目が空なら飛ばし、同一番号の重複と複数 Main は拒否します (`strata_control/gpu_roles.py:218-244`)。Main が省略されると setup CLI は有効指定の最大カード番号を Main にし、Helper と Main の順で GPU 指定を作ります (`setup.py:9755-9765`)。setup が確定したカード群について `gpu_roles` を保存し、複数カードなら `gpu_order: as_given` も保存します (`setup.py:10886-10893`)。

server は保存済みの `gpu_roles` が有効な場合、Main を最後に置き、Off を除外した順を使います。設定に対応する `gpu` が残っていればそちらを使います (`serve/server.py:3298-3305`)。この環境変数の参照箇所に、OS / CUDA・HIP・SYCL 別の値判定や cache はありません。適用範囲は Docker entrypoint と setup/server の設定経路です。

## 根拠

- 候補一覧には `GPU_ROLES` が記載されています (`docs/envvars/000_envvers.md` の該当項目)。Strata ソース内の完全一致検索では、値を読む実装は `docker/entrypoint.sh:220` のみでした。その他の一致は entrypoint の説明コメント、Docker / Multi-GPU の説明資料です。
- Docker の環境変数表も `GPU_ROLES` を `launch --gpu-roles` に渡すと記載しており、entrypoint の実装と一致します (`docs/DOCKER.md:124`, `docs/MULTI_GPU.md:41`)。
- 調査対象は Strata 所有ソースの上記 commit です。外部ライブラリや GPU driver が読む環境変数名の挙動は含めていません。
