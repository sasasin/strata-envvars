# `STRATA_CPUINFO`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Docker イメージの entrypoint が AVX2 警告を出す際に調べる CPU 情報ファイルのパスを指定します。既定では `/proc/cpuinfo` を調べます。エンジンの CPU 機能設定を変える環境変数ではなく、entrypoint の事前警告だけに使われます。

## 値と判定

entrypoint はシェルの `${STRATA_CPUINFO:-/proc/cpuinfo}` で値を選びます。

| 値 | 読み取り先 |
|---|---|
| 未設定または空文字 | `/proc/cpuinfo` |
| 空でない文字列 | その文字列をファイルパスとして使用 |

値の形式、ファイル内容の CPU 名や数値は parse しません。指定パスが読み取り可能で、その中に `flags` で始まる行があり、最初の `flags` 行に単語 `avx2` がなければ、stderr に次の警告を出します。

```text
[!] This computer's CPU has no AVX2. The engine is built for CPUs with AVX2 and may stop with 'illegal instruction'.
```

読み取り不可または `flags` 行なしの場合は警告しません。`grep -w avx2` による単語判定なので、`avx2` を含む別の長い単語だけでは一致しません。大小文字変換や CPU 情報の別形式への変換はありません。

## 有効になる条件

この参照は `docker/entrypoint.sh` にあります。引数なし、または `run` / `serve` で通常のサーバー起動経路に進む場合、entrypoint の「plain warnings」段階で評価されます。`sh` や `strata ...` など、別コマンドを指定した場合はスクリプト冒頭で `exec` するため、この判定に到達しません。

Docker entrypoint がこの環境変数を参照するので、コンテナ起動時に設定された値が対象です。スクリプトはこの値を起動時の判定に使います。Strata の他のソースに同名変数を読む箇所は見つからず、エンジンの動作を変える用途ではありません（環境変数自体は通常のプロセス環境として子プロセスに継承され得ます）。

## 実行時の詳細

シェル変数 `cpuinfo` にパスを設定し、`[ -r "$cpuinfo" ]`、`grep -q '^flags'`、最初の `flags` 行に対する `grep -qw avx2` の順で判定します。AVX2 が見つからない場合も `warn` 関数で注意を出すだけで、終了や起動拒否はしません。直後も通常の entrypoint 処理を続け、最終的に `strata launch` を起動します。

`docs/DETAILS.md` にこの変数に関する説明や測定値は見つかりませんでした。Docker entrypoint のソースで確認できる用途は上記の警告です。

## 根拠

- `docker/entrypoint.sh:41-44`: 通常起動以外のコマンドを `exec` し、後続の警告判定を通らない経路。
- `docker/entrypoint.sh:55-59`: 既定パス、読み取り可否、`flags` 行および AVX2 の判定、警告文。
- `docker/entrypoint.sh:124-138, 157-159` および後続の起動処理: 警告とは別に engine 確認と `strata launch` の準備を続ける通常経路。
- `tools/test_docker_entrypoint.py:58`: テストが `STRATA_CPUINFO` を一時ファイルに向けていることを確認。これはテスト用の手掛かりとしてのみ参照し、挙動の根拠にはしていません。
