# `strata --serve`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数。Terminal CLI の `strata serve` とは別） |
| オプション | `--serve` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

モデル等の起動時リソースを読み込んだ後、プロセスを終了させず、stdin からリクエストを受け付ける常駐モードにします。推論結果と状態通知は stdout に出ます。これはエンジン内の stdin/stdout プロトコルを有効にするフラグであり、このオプションだけで HTTP サーバーの待受を開始する実装ではありません（`src/program/generate.cpp:9543-9564,13776-13777`）。

## 使い方

```sh
strata --pack /path/to/model-pack --serve --spec 4 --prefill auto
```

`--pack` は使用するモデル pack、`--spec` は検証ウィンドウ、`--prefill` は prompt 処理 chunk の設定例です。serve 起動時には `--spec` が 2 以上であることと、prefill chunk が正であることが必要です。実際の受理条件は下記「適用条件と副作用」を参照してください（`src/program/generate.cpp:10444-10449`）。

## 値と既定値

- 値を取りません。parser は `--serve` を見つけると `o.serve = true` にします。既定値は `false` で、同じ引数を複数回指定しても true のままです（`src/program/generate.cpp:917-918,3364-3368,3585-3587`）。
- 引数がない場合、serve モードはリクエストごとに prompt token を受け取るため、起動時の `--tokens` を要求しません。内部では sentinel token、`max_new=1`、`stop_eos=true` を設定します（`src/program/generate.cpp:4240-4250`）。
- `--serve` 自体に値の validation はありません。値を付けたつもりで `--serve something` とすると `something` は別引数として処理され、未知引数なら usage とともに stderr に出て終了コード 2 になります（`src/program/generate.cpp:3755-3760`）。

## 実行時の動作

- `--serve` が有効な場合、起動済みのモデル重み・expert arena・VRAM tier を保持したまま、stdin から行単位でリクエストを読みます。通常の text request は `GEN <max_new> <id,id,...>` 形式で、生成 token ごとに `T <id>`、最後に `DONE ...` を stdout に出します。読み込み進捗は `RESUME`、`PP`、`REUSED` などで通知します（`src/program/generate.cpp:9543-9564,13776-13777,15471-15480,16471-16473,19269-19292`）。
- stdin reader は別 thread で動き、`STOP` は実行中 request の停止フラグを立て、`QUIT` はリクエストループを終了します。入力が閉じられた場合もループを終えます（`src/program/generate.cpp:13499-13558,15200`）。
- 画像 request の `GENI` は `--vision` が有効な起動でのみ受け付けます。未指定時に `GENI` が来ると `ERR this engine was started without --vision` を stdout に出して、その request を続行しません（`src/program/generate.cpp:13830-13834,15471-15474,15631-15633`）。
- `--serve` がない通常実行では一回分の token input が必要で、`--tokens` または token file がなければ stderr に必須エラーと usage を出し、終了コード 2 になります（`src/program/generate.cpp:4246-4250`）。

## 適用条件と副作用

- 起動処理で `--spec < 2`、`--prefill` chunk が 0 以下、または graphed hit path の必要な expert cache/profile が満たされない場合は、`strata serve: needs --spec T and --prefill CHUNK ...` を stderr に出して終了コード 2 になります。`--spec` の初期値は Metal build で 2、それ以外では 0 なので、非 Metal の通常 build では明示指定が必要です（`src/program/generate.cpp:848-852,10444-10449`）。
- 会話 checkpoint は既定で最大 6 個を保持し、parked conversation cache は最大 4 slot です。serve 中の RAM 使用を抑えたい場合などに `--prompt-cache`、`--conversation-cache-mib`、`--conversation-cache-slots` 等で調整できます。`--prompt-cache 0` または `--conversation-cache-slots 0` と正の cache budget が併存すると、cache 無効化の warning が stderr に出ます（`src/program/generate.cpp:922-928,4005-4007`）。
- `--batch` は serve 専用で、2 slot 未満や同一 GPU の layer split 等の条件では warning を出し batch を無効化します。`--layer-split` は `--serve` が必要で、条件不成立なら stderr に理由を出し終了コード 2 になります（`src/program/generate.cpp:853-856,4047-4057,4092-4097,6853-6859`）。
- `--remote-expert-opt` も `--serve` が必須で、単独使用は stderr にエラーを出し終了コード 2 です（`src/program/generate.cpp:4466-4469`）。他にも serve 条件を持つオプションがありますが、それら個別の値・副作用は各オプション文書を参照してください。
- 起動時に model と GPU/CPU 側の実行資源を準備し、終了まで保持します。会話の再利用 checkpoint や、別オプションによる batch slot、layer split、画像 embedding の読み込みも serve 経路の副作用です（`src/program/generate.cpp:9543-9564,13776-13777,15648-15665`）。OS/backend ごとの全 build を実行しての確認はしていません。

## 出力とエラー

- 起動準備完了後、stdout に `READY <max_context> stop` を出します（`src/program/generate.cpp:13774-13777`）。通常 request は token 単位の `T <id>` と完了時の `DONE ...` を出します（`src/program/generate.cpp:18374,18950,19284-19292`）。
- 不正な request は、たとえば形式不一致なら `ERR expected: GEN ... or GENI ...`、prompt と生成長の合計が context を超える場合は `ERR prompt ... exceeds the context ...` を stdout に出し、その request をスキップします（`src/program/generate.cpp:15471-15474,15726-15729`）。
- NaN/Infinity を含む logits の window は、その window の token を出力せず `DONE ... nonfinite` として終了し、次の request は token 0 から読み直します（`src/program/generate.cpp:9554-9557,12178-12184`）。
- `--serve` に固有の数値終了コードは parser にありません。ここに記した起動時 validation は 2、入力不備は常駐中の `ERR` 応答です。GPU 等の実行時障害で終了する全経路の終了コードはこのオプション単体では一律に定まりません。

## 根拠

- option の宣言と既定値: `src/program/generate.cpp:917-918`。
- parser: `src/program/generate.cpp:3364-3368,3585-3587`。
- serve 時の起動引数補完と tokens 必須条件: `src/program/generate.cpp:4240-4250`。
- serve mode 固有の起動 validation: `src/program/generate.cpp:10444-10449`。
- stdin/stdout 常駐経路と protocol: `src/program/generate.cpp:9543-9564,13499-13558,13774-13777,15200,15471-15480,19269-19292`。
- 索引上の scope: `docs/cli/README.md` の `strata-engine` → `strata`（エンジン引数）節。Qwen3.6 専用 parser は別の `strata-engine/qwen36/` scope で、本書の対象外です。
