# `--experimental-speed-projection`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などの wrapper 経由） |
| オプション | `--experimental-speed-projection` |
| 別名 | なし |
| 値 | `on` / `off`、または control vector の GGUF ファイルパス |

## 役割

実験的な control vector をモデル設定に読み込ませ、推論時に projection を適用するか選びます。オプションは `setup.py` に定義され、対応するセットアップではベクトルの選択結果をエンジン引数としてモデルの run config に保存します。[`setup.py:8457-8459`](../../../../../../Niko1221/Strata/setup.py#L8457)

## 使い方

Qwen または Coder の初回セットアップ／設定変更時に指定します。

```sh
./setup.sh --setup --experimental-speed-projection on
```

Windows では `START-HERE.bat --setup --experimental-speed-projection on` を使えます。POSIX wrapper は全引数を `setup.py` に渡し、Windows wrapper も `%*` を渡します。[`setup.sh:6-12,76`](../../../../../../Niko1221/Strata/setup.sh#L6) [`START-HERE.bat:8-10,48-54`](../../../../../../Niko1221/Strata/START-HERE.bat#L8)

## 値と既定値

- 値は必須です。parser は自由形式の文字列として受け取り、`choices` や独自の値型検査はありません。省略時は内部値が未指定（`None`）です。[`setup.py:8457-8459`](../../../../../../Niko1221/Strata/setup.py#L8457)
- 比較時に前後の空白を除き、大文字小文字を区別しません。`off` / `no` / `n` / `0` は無効化、`on` / `yes` / `y` / `1` は同梱ベクトルを選びます。[`setup.py:9179-9192`](../../../../../../Niko1221/Strata/setup.py#L9179)
- 上記以外の値はファイルパスとして解釈し、`~` を展開して絶対パスに変換します。`--experimental-speed-projection` の後に値を付けなければ、`argparse` が usage とエラーを表示して終了します（通常の argparse の終了コード 2）。[parser 定義 `setup.py:8420-8421,8457-8459`](../../../../../../Niko1221/Strata/setup.py#L8420) [`argparse` 呼び出し `setup.py:8553`](../../../../../../Niko1221/Strata/setup.py#L8553)
- Qwen / Coder で値を省略した場合は対話で確認し、既定回答は「いいえ」です。したがって通常の省略時は off です。同梱 GGUF の場所は `data/experimental-speed-projection/Qwen3.8-Flash-Next-experimental-speed-projection.gguf` です。[`setup.py:792-793,9181-9188`](../../../../../../Niko1221/Strata/setup.py#L792)

## 実行時の動作

対応する family で有効値を選ぶと、セットアップは同梱 GGUF または指定パスを確認します。setup が確認するのはファイルの存在までで、GGUF の形式や vector tensor の内容はエンジン側で読み込み時に検証されます。ファイルが存在しなければ `[X]` メッセージを表示して setup を終了コード 1 で停止します。存在すればエンジン引数 `--control-vector-scaled <path>:1.0 --control-vector-layer-range 4 44 --cvec-mode project --cvec-dir per-layer` を追加します。[`setup.py:9189-9196,9593-9597`](../../../../../../Niko1221/Strata/setup.py#L9189) [`fail()` `setup.py:825-830`](../../../../../../Niko1221/Strata/setup.py#L825)

エンジンは control vector GGUF の `general.architecture=controlvector`、`direction.<layer>` tensor の存在・型・幅を確認します。読み込みに失敗すると `strata generate: control vector: ...` を stderr に出し、終了コード 2 を返します。[`src/program/generate.cpp:1863-1901,3963-3968`](../../../../../../Niko1221/Strata/src/program/generate.cpp#L1863)

この引数列はモデルの run config に含まれ、setup が設定を書き込みます。設定更新時は既存の config を `.bak` に保管する場合があります。[`setup.py:9593-9599`](../../../../../../Niko1221/Strata/setup.py#L9593) [`write_setup_config()` `setup.py:6312-6347`](../../../../../../Niko1221/Strata/setup.py#L6312)

エンジンは各レイヤーの residual stream 書き込み後、対象レイヤーで control vector を適用します。[`src/core/layer.cpp:1615-1626`](../../../../../../Niko1221/Strata/src/core/layer.cpp#L1615) ベクトルがロードされた後は、リクエストごとに `experimental_speed_projection: false` を指定すればそのリクエストでは無効化できます。server は bool 値を `cvec=0|1` のエンジン要求キーに変換し、bool 以外はそのキーにしません。リクエスト値が省略された場合は有効扱いです。[`serve/server.py:1461-1466`](../../../../../../Niko1221/Strata/serve/server.py#L1461) パッケージ README は UI/API からの切り替えも説明しています。[`data/experimental-speed-projection/README.md:15-17`](../../../../../../Niko1221/Strata/data/experimental-speed-projection/README.md#L15)

## 適用条件と副作用

- `family` が `qwen` または `coder` のときだけ値を適用します。それ以外の family では off / no / n / 0 / 空値以外を警告し、設定は off のままにします。Swift は元の Qwen3.8-Flash-Next 用である旨、それ以外は当該モデルで未テストである旨の警告です。[`setup.py:9181-9196`](../../../../../../Niko1221/Strata/setup.py#L9181)
- parser 自体はプラットフォーム限定にしていません。ただし macOS の通常 Metal setup は `metal/setup_mac.py` に引数を渡す別 parser へ分岐し、その parser にこのオプション定義はありません。Control mode の macOS も `mac_control_setup()` へ早期分岐するため、この ESP 処理には到達しません。[`setup.py:8418-8419,8561-8564`](../../../../../../Niko1221/Strata/setup.py#L8418) [`metal/setup_mac.py:327-355`](../../../../../../Niko1221/Strata/metal/setup_mac.py#L327)
- `--update` は ESP の設定処理に入る前に更新関数へ戻ります。既存モデルを通常起動する経路も、保存済み config から直接起動します。したがって、このオプションを既存 config に反映させるには `--setup` などセットアップ経路を選びます。[`setup.py:8617-8619`](../../../../../../Niko1221/Strata/setup.py#L8617) [`setup.py:8677-8682`](../../../../../../Niko1221/Strata/setup.py#L8677)
- 同梱ベクトルの説明では、これは推論エンジンの高速化機能ではなく、拒否方向の projection によってモデルの応答を変え、安全動作を弱める可能性があるとされています。通常の出力も変化し得ます。これはパッケージ README の説明であり、CLI ソースでの独立した性能検証ではありません。[`data/experimental-speed-projection/README.md:7-13`](../../../../../../Niko1221/Strata/data/experimental-speed-projection/README.md#L7)

## 出力とエラー

Qwen / Coder で省略した際は、実験機能と既定 off を説明して質問を表示します。有効時／無効時はいずれも setup が状態を表示します。ベクトルが見つからない場合は setup が停止します。対応外モデルで有効値を与えた場合は警告し、off にします。[`setup.py:9181-9196`](../../../../../../Niko1221/Strata/setup.py#L9181)

## 根拠

- parser、値の解釈、family 条件、エラー: [`setup.py:825-830,8420-8421,8457-8459,8553,9177-9196`](../../../../../../Niko1221/Strata/setup.py#L8457)
- engine 引数、run config、保存処理: [`setup.py:9593-9599,6312-6347`](../../../../../../Niko1221/Strata/setup.py#L9593)
- エンジンの vector 読み込み検証と適用箇所: [`src/program/generate.cpp:1863-1901,3963-3968`](../../../../../../Niko1221/Strata/src/program/generate.cpp#L1863)、[`src/core/layer.cpp:1615-1626`](../../../../../../Niko1221/Strata/src/core/layer.cpp#L1615)
- wrapper の引数委譲: [`setup.sh:6-12,76`](../../../../../../Niko1221/Strata/setup.sh#L6)、[`START-HERE.bat:8-10,48-54`](../../../../../../Niko1221/Strata/START-HERE.bat#L8)
- リクエスト単位の切り替え: [`serve/server.py:1461-1466`](../../../../../../Niko1221/Strata/serve/server.py#L1461)
- パッケージの説明: [`data/experimental-speed-projection/README.md:1-17`](../../../../../../Niko1221/Strata/data/experimental-speed-projection/README.md#L1)

調査時の Strata checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。CLI `--help` の実行、build、性能測定、テストは行っていません。
