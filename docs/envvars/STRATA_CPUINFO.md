# `STRATA_CPUINFO`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata Docker image の entrypoint が、CPU の AVX2 フラグ有無を確認するファイルのパスを差し替えるための環境変数です。エンジンの設定には使われず、通常の Docker 起動経路で警告を出すかどうかの確認にだけ使われます。

## 値と判定

| 状態 | entrypoint が使うパス | 結果 |
|---|---|---|
| 未設定 | `/proc/cpuinfo` | この既定ファイルを確認 |
| 空文字 | `/proc/cpuinfo` | `${STRATA_CPUINFO:-...}` の `:-` 展開により既定ファイルを確認 |
| 空でない値 | 値をそのままファイルパスとして使用 | パスの読み取り可否と内容を確認 |

値を数値や真偽値には変換せず、範囲検査もしません。パスは引用して検査・読み取りに渡されるため、空白を含むパスも一つのパスとして扱われます。CLI 引数や別環境変数による同じパスの上書きはありません。

## 有効になる条件

この変数は `docker/entrypoint.sh` が通常起動を続ける経路で評価されます。引数が `run` または `serve` 以外のコマンド（たとえば `sh` や `strata ...`）なら、entrypoint は先に `exec` するため CPU 判定に到達しません。

通常経路では、指定ファイルが読み取り可能で、少なくとも一つ `^flags` に一致する行がある場合に限り、その最初の `flags` 行を調べます。その行に単語 `avx2` がなければ警告を出します。ファイルが読めない、または `flags` 行がない場合は警告しません。CPU backend、モデル状態、GPU backend、他の Strata 環境変数による追加条件は、この判定にはありません。

## 実行時の詳細

entrypoint が通常経路へ進んだ時点でシェル展開により一度パスを決め、`-r` と `grep` で確認します。値を Strata バイナリや子プロセスへ設定・転送する処理はありません。判定は起動前の案内であり、警告を出しても停止・終了コード変更は行わず、その後の entrypoint 処理を続けます。警告文は stderr に `[!] ` を付けて出力されます。

- AVX2 が見つからない場合: `This computer's CPU has no AVX2. The engine is built for CPUs with AVX2 and may stop with 'illegal instruction'.`
- AVX2 が見つかった場合、または検査条件を満たさない場合: この判定からは出力しません。

## 根拠

- `docker/entrypoint.sh:53-56` — `run` / `serve` 以外の引数では先にコマンドを `exec` し、判定を通らない。
- `docker/entrypoint.sh:67-70` — 未設定・空値の既定パス、読み取り可否、`flags` 行と最初の行の `avx2` 検査、警告文。
- `docker/entrypoint.sh:37-39` — `warn` は `[!] ` を付けて stderr に出力する。CPU 判定からは `die` を呼ばない。
- `tools/test_docker_entrypoint.py:58-59` — entrypoint テストは一時的な `STRATA_CPUINFO` ファイルを渡している。このテスト参照は実装挙動の根拠には用いていない。
