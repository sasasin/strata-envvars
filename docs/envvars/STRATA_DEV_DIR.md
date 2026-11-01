# \`STRATA_DEV_DIR\`

調査対象: Strata \`main\` の HEAD \`c62d5e3a15b40ea51c96aae9e8d36928965f53ab\`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Docker entrypoint が、検出した GPU backend に対応する device node を確認するディレクトリを指定します。デバイスファイルを別の場所に見せる構成で、起動前の存在確認先を \`/dev\` から変更できます。この値は Strata エンジンの設定や \`strata launch\` の引数には変換されず、entrypoint 内のシェル変数 \`dev\` としてのみ使われます。

リポジトリ内の全参照を検索すると、本番コードでの読み取りは \`docker/entrypoint.sh:155\` のみです。ほかの一致は \`tools/test_docker_entrypoint.py:231,237\` のテストコードです。

## 値と判定

POSIX shell の \`\${STRATA_DEV_DIR:-/dev}\` で読みます。

| 値 | \`dev\` の値 | 動作 |
|---|---|---|
| 未設定 | \`/dev\` | 標準の \`/dev\` 以下で backend 別の device node を確認 |
| 空文字 | \`/dev\` | 未設定と同じ。空文字を明示しても空のパスにはならない |
| 空でない文字列 | 指定文字列そのまま | そのディレクトリ以下を確認。数値変換、文字列正規化、存在確認、値域検査はしない |

空白や相対パスを含む値も拒否されません。パスを組み立てるとき \`"$dev"\` は引用され、末尾に backend ごとのファイル名パターンが連結されます。パスの実在性や適切さは、その後の \`ls\` / \`test -e\` の結果で間接的に判定されます。

## 有効になる条件

- Docker image の entrypoint が \`run\` または \`serve\` として通常のサーバー起動経路を続ける場合に読み取ります。Dockerfile は \`/opt/strata/entrypoint.sh\` を entrypoint として起動します。
- 引数があり、先頭が \`run\` / \`serve\` 以外なら、entrypoint は Strata コマンドまたは指定コマンドを直接 \`exec\` するため、この変数を読みません。引数なしで起動した場合は通常経路です。
- Strata の \`components engine --output json\` が usable な engine を返した後、JSON から \`backend\` を取り出して分岐します。engine が usable でなければ、この変数を読む前に終了します。
- backend が \`cuda\`、\`hip\`、\`sycl\` の場合にそれぞれの確認をします。ほかの backend 名では \`case\` に該当せず、device node の確認を行いません。

## 実行時の詳細

読み取りは entrypoint のサーバー起動処理中、engine の usable 判定後かつ API key・launch 設定の処理前に一度だけ行われます。以後の確認にはローカル変数 \`dev\` を使います。子の \`strata launch\` に \`STRATA_DEV_DIR\` を設定し直したり、CLI 引数として渡したりする箇所はありません。プロセス環境が起動後に変わる場合の再読込もありません。

backend ごとの判定は次のとおりです。

| backend | 確認内容 | 見つからない場合 |
|---|---|---|
| CUDA | \`$dev/nvidia[0-9]*\` に一致する項目を \`ls\` できる、または \`$dev/dxg\` が存在する | stderr に「This computer has an NVIDIA card, but the container cannot use it, so nothing would run (and the model would be prepared for nothing). Start the container with: --gpus all ...」を出して status 3 で終了 |
| HIP | \`$dev/kfd\` が存在する | stderr に「This is an AMD card, but /dev/kfd is not in the container. Add: --device /dev/kfd --device /dev/dri --group-add video --group-add <render group number> (docs/DOCKER.md)」を出して status 3 で終了 |
| SYCL | \`$dev/dri/renderD*\` に一致する項目を \`ls\` できる | stderr に「This is an Intel card, but /dev/dri is not in the container. Add: --device /dev/dri --group-add <render group number> (docs/DOCKER.md)」を出して status 3 で終了 |

CUDA と SYCL はシェル glob を使い、一致がない場合は失敗します。HIP は単一パスの \`test -e\` です。HIP/SYCL の失敗メッセージに表示される \`/dev/kfd\` と \`/dev/dri\` は固定文字列で、\`STRATA_DEV_DIR\` の値を反映しません。確認に成功すれば通常の entrypoint 処理を続け、失敗時はモデル準備へ進みません。

## 根拠

- \`docker/entrypoint.sh:53-56\` — 直接コマンドの経路では \`exec\` して、通常の初期化を迂回します。
- \`docker/entrypoint.sh:136-160\` — engine の usable 判定、backend の抽出、環境変数の既定値、CUDA/HIP/SYCL の device node 確認、終了コードとエラーメッセージ。
- \`docker/entrypoint.sh:162-170,252-282\` — device 確認後の API key・launch 引数設定と子プロセス起動。
- \`Dockerfile:100-111\` および \`docker/Dockerfile:87-89,130-134\` — entrypoint スクリプトを image に含め、コンテナの entrypoint として起動します。両方の Dockerfile に \`STRATA_DEV_DIR\` の既定値設定はありません。
