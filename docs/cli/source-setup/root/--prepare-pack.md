# `setup.py --prepare-pack`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`root/` scope） |
| オプション | `--prepare-pack` |
| 別名 | なし |
| 値 | 必須の出力先ディレクトリ `PACK_DIR` |

## 役割

指定済みの GGUF モデルから、Intel Arc など通常の setup が用意しない実行環境向けの model pack を作ります。pack にはエンジンが読む index、dense weights、tokenizer、expert table が含まれます。このモードは pack 準備だけを行い、モデルのダウンロード、engine の build、server の起動、run config の作成には進みません。

## 使い方

```sh
python setup.py --prepare-pack /path/to/pack \
  --gguf-dir /path/to/model-ggufs --family qwen --model IQ3_XXS
```

`--gguf-dir` はモデルの GGUF shard を含むフォルダ、`--family` と `--model` はそのファイルに対応する Strata の選択値です。`--family` を省くと `qwen` として扱われます。

## 値と既定値

- `PACK_DIR` は `argparse` の値引数で、値の形式・存在確認・絶対パス化などの専用 validation はありません。pack tool 側が出力先を作成します（`setup.py:9658-9660`; `tools/iq_pack.py:610-613`）。
- `--gguf-dir` は parser 上は任意ですが、このモードでは必須です。未指定なら `--prepare-pack needs --gguf-dir...` を表示して終了コード 1 になります（`setup.py:9325-9326`）。
- `--family` の省略値は `qwen`。handler が受け付ける family は `FAMILIES` にあるものに限られ、parser が受け付ける preview / multi-file family を選んでも pack handler では拒否されます（`setup.py:9327-9330,9569-9572`）。
- `--model` は parser の `model_alias` と choices により検査されますが、この handler でも必須です。省略時はエラーになります（`setup.py:195-199,9573-9575,9330-9332`）。
- `--prepare-pack` のデフォルトは明示指定されていません。省略するとこの分岐に入らず、通常の setup 経路になります（`setup.py:9658-9660,9717-9725`）。

GGUF shard は選択モデルの公開名を優先し、見つからない場合は名前に model 値を含む shard 1 を候補にします。ファイル名の `-00001-of-0000N.gguf` から shard 一覧を組み立てます。選択ファイルが未対応 quantization である場合や、フォルダ内の別 GGUF から選択不一致を判別できる場合は、利用可能な family/model 候補を添えて拒否します（`setup.py:3222-3245,3271-3298`）。

## 実行時の動作

1. `setup.py` の parser が `PACK_DIR` を `a.prepare_pack` に入れます。`main()` は `--prepare-pack` が truthy なら、他の setup mode 判定より先に `prepare_pack_only()` を呼び、その戻り値を終了値にします（`setup.py:9658-9660,9717-9725`）。
2. 指定 GGUF の shard 1 を特定し、`gguf_dir_problem()` の選択・対応形式チェックを通します。完全な shard 集合の検査や GGUF 内容の検証は pack tool 側でも行われます（`setup.py:9333-9337,3225-3244,3271-3298`; `tools/iq_pack.py:615-620`）。
3. `get_llama_cpp()` は `home()/third_party/llama.cpp` に必要な `gguf-py` があれば再利用し、なければ Strata が pin した llama.cpp zip を取得・展開します。モデル本体の取得ではありません（`setup.py:9340-9345,3615-3645`）。
4. `tools/iq_pack.py` を `--gguf <shard 1> --out <PACK_DIR>` で実行し、`STRATA_GGUF_PY` に helper の `gguf-py` パスを設定します。family 固有の `pack_args` があれば追加します（`setup.py:9342-9345`）。この呼び出しは `--base` / `--skip-experts` / `--experts-bin` を渡さないため、pack tool の既定動作で index、dense weights、tokenizer、`native_experts.txt` 等を準備し、通常は GGUF 本体から `experts.bin` を作りません（`tools/iq_pack.py:595-605,700-726`）。
5. `setup.py` は `tokenizer/vocab.json` の存在を最終確認し、成功時に `model prepared: PACK_DIR` を表示して 0 を返します。既に `native_experts.txt` と `tokenizer/vocab.json` が両方ある場合、pack tool の再実行を省略します（`setup.py:9343-9349`）。

## 適用条件と副作用

- 想定用途は、手元にある対応 GGUF から pack を作ることです。setup.py は GGUF モデルをダウンロードも変更もしないと handler の docstring に明記しています（`setup.py:9321-9324`）。
- llama.cpp helper が未配置の場合はネットワーク取得が発生し、`home()/third_party/` 以下に archive、展開物を置きます。`tools/iq_pack.py` は `PACK_DIR` を作成し、その中の pack ファイルを生成・更新します（`setup.py:3615-3645`; `tools/iq_pack.py:610-613,700-726`）。
- pack tool は既存の `hadamard.txt` を不要な場合に削除し、completion marker や index/dense ファイルを一時ファイルから置換する経路があります。既存 pack を指定する場合は、その出力先が変更され得ます（`tools/iq_pack.py:336-346,713-722`）。setup.py の skip 条件は completion marker と vocab の存在だけを確認し、入力 GGUF と pack の一致まではこの箇所で比較しません（`setup.py:9343-9347`）。
- `strata launch` は Intel Arc の SYCL 経路で、shard が見つかり、pack の必要ファイルが揃っていないときにこのオプションを内部実行します。直接実行する場合と異なり、launch 側は `STRATA_CONTROL_INSTALL=1` などを子プロセス環境に設定します（`strata_cli/launch/runner.py:1319-1336,1370-1376`）。
- macOS で `STRATA_CONTROL_INSTALL` を設定せずに setup.py を起動すると、parser 構築前に `metal/setup_mac.py` へ委譲されます。このオプションが同じ動作をするとは確認できないため、ここで記述した適用範囲は setup.py 自身の parser が動く経路です（`setup.py:9560-9568`）。
- `--source` は parser 後に `STRATA_SOURCE` 環境変数へ反映されますが、この分岐ではモデル取得をせず、helper は pinned archive を使います（`setup.py:9721-9724,3615-3622`）。他の setup option はこの専用分岐より後の処理に影響しません。

## 出力とエラー

- `--gguf-dir` / `--model` 不足、未対応 family、GGUF の選択・形式問題は `fail()` が `[X]` と案内を出し、終了コード 1 で停止します（`setup.py:965-970,9325-9337`）。
- pack tool の実行が非ゼロで終わる場合、共通 `run()` が失敗したコマンドと終了値を表示して setup を終了します。helper の取得・展開に関する I/O 例外や pack tool の例外も発生し得ますが、個々の例外文面・終了値はこのオプション文書の範囲では固定できません（`setup.py:1020-1042,9340-9345`; `tools/iq_pack.py:615-620`）。
- pack tool が完了しても `tokenizer/vocab.json` がなければ終了コード 1 です。`chat_template.jinja` など、他の pack ファイルを setup.py が同様に最終確認するわけではありません（`setup.py:9346-9348`）。
- `strata launch` からの内部実行が失敗した場合は `[X]` 行を launch error に含め、準備ログまたは launch log の場所を案内します（`strata_cli/launch/runner.py:1348-1352`）。

## 根拠

- `setup.py:9568-9660` — parser と `--prepare-pack` の値引数定義。
- `setup.py:9717-9725` — parser 後の前処理と、専用 handler への早期分岐。
- `setup.py:9321-9349` — 必須値、family/model 検証、GGUF 選択、helper 準備、pack 作成、成功判定。
- `setup.py:3222-3244,3271-3298` — shard 名の認識、GGUF 選択エラーの判定。
- `setup.py:3615-3645` — pinned llama.cpp helper の再利用・取得・展開。
- `setup.py:1020-1042` — helper tool の起動と非ゼロ終了時の処理。
- `tools/iq_pack.py:595-620,700-726` — pack tool の parser と pack 出力処理。
- `strata_cli/launch/runner.py:1319-1352,1370-1376` — Terminal CLI が Intel Arc 用 pack を内部準備する条件と失敗伝播。

## 関連文書

- [CLI 索引](../../README.md) — `source-setup` の他の option 文書と scope。
