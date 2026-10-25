# `--pack`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--pack` |
| 別名 | なし |
| 値 | pack ディレクトリのパス（`DIR`） |

## 役割

推論に使うモデル pack のディレクトリを指定します。エンジンはこの場所の `index.txt` を読み、重みをロードします。pack の形式によっては、専門家重みの配置情報 `native_experts.txt` などもこのディレクトリから読みます。pack を作成するオプションではありません。(`src/program/generate.cpp:806-812, 3458-3465`; `src/core/weights.cpp:93-97, 176-180`)

## 使い方

```sh
strata --pack /path/to/pack --tokens "1,2,3"
```

このエンジンの例は事前 token 化済み ID を `--tokens` で渡します。通常起動では pack ディレクトリ内に `index.txt` が必要です。(`src/program/generate.cpp:808-812, 3174-3179`; `src/core/weights.cpp:176-180`)

## 値と既定値

- 値はディレクトリのパス文字列です。相対パスの場合、コードはそのまま `pack_dir + "/ファイル名"` を組み立てて開くため、プロセスの作業ディレクトリを基準に解決されます。(`src/core/weights.cpp:93-97, 176-180`; `src/kernels/cpu/expert_layout.cpp:388-393`)
- 省略時は `pack/full` です。(`src/program/generate.cpp:418-420, 806-812`)
- parser は値が省略された場合に `--pack needs a value` を stderr に出し、終了コード 2 で終了します。値のパス自体は parser では検証しません。同じオプションを複数回指定した場合は、ループ内で `o.pack` を都度代入するため最後の値が使われます。(`src/program/generate.cpp:2416-2425`)

## 実行時の動作

起動後、`--pack` の値は専門家重みの layout 判定に渡されます。`native_experts.txt` がなければ layout loader は canonical pack として扱い、ファイルがあれば native expert metadata を読み込みます。native metadata の形式バージョン、各層の行・offset・blob サイズ、Hadamard metadata の整合性などが検査されます。(`src/kernels/cpu/expert_layout.cpp:388-407, 412-445, 483-509`)

続いて `index.txt` から重み領域のサイズを求め、そのファイルの各行を解析して重みをロードします。読み込み成功後は、stderr にロードした MiB 数と pack パスが表示されます。(`src/core/weights.cpp:93-122, 176-239`; `src/program/generate.cpp:3852-3855, 3896-3909`)

`native_experts.txt` を持つ native (IQ) pack では、`--pack` に加えて `--native SHARD1`、`--spec` 2 以上、および複数 token prompt 時の正の `--prefill` chunk が必要です。満たさない場合は stderr に要件を出し、終了コード 2 で終了します。(`src/program/generate.cpp:3458-3465, 3753-3765`)

## 適用条件と副作用

- このオプションは `src/program/generate.cpp` の推論エンジン parser のスコープです。Qwen3.6 など別 family へ parser 前に振り分けられる条件では、別実装側が引数を処理する場合があります。この文書ではその family 固有の挙動を扱いません。通常 engine の引数 parser と Qwen3.6 振り分けは `src/program/generate.cpp:2393-2408, 2413-2425` にあります。
- pack のロードにより重み領域を GPU に確保し、重みデータを読み込みます。GPU 実行環境や pack のファイル内容に依存するため、ここでは特定の backend での成功を保証しません。(`src/program/generate.cpp:3852-3887, 3896-3910`)
- 追加の環境変数による `--pack` パスの上書きは確認できません。native pack の読み込み経路で `--native` の GGUF shard も使われる条件は上記のとおりです。(`src/program/generate.cpp:3753-3765`)

## 出力とエラー

- `index.txt` が開けない場合、`cannot open <pack>/index.txt`（または loader の案内付きエラー）を stderr に出して終了コード 1 で終了します。`index.txt` の header/row が欠落または不正な場合もエラーになります。(`src/core/weights.cpp:93-122, 176-239`; `src/program/generate.cpp:3852-3855, 3896-3900`)
- `native_experts.txt` の形式・version・layer 配置が不正、あるいは対応しない native metadata の場合、layout loader のエラーを stderr に出し、終了コード 1 で終了します。native metadata がないこと自体はエラーではなく canonical pack として扱われます。(`src/kernels/cpu/expert_layout.cpp:392-401, 412-445, 483-509`; `src/program/generate.cpp:3461-3465`)
- `--tokens` も `--tokens-file` もなく、serve mode でもない場合、`--tokens is required` と usage を stderr に出して終了コード 2 で終了します。これは `--pack` 固有の検証ではありません。(`src/program/generate.cpp:3168-3179`)

## 根拠

- `src/program/generate.cpp:418-420, 806-812` — pack パスの既定値、usage と値の説明。
- `src/program/generate.cpp:2416-2425` — parser が値を取得して `o.pack` に設定する箇所。
- `src/program/generate.cpp:3458-3465, 3753-3765, 3852-3909` — pack metadata のロード、native pack の条件、重み読み込みと出力。
- `src/kernels/cpu/expert_layout.cpp:388-509` — native expert metadata の有無と検証。
- `src/core/weights.cpp:93-122, 176-239` — `index.txt` による重み領域計算と index の検証・読み込み。
- `docs/cli/README.md:1128-1134, 1240` — `strata-engine` の parser scope とこの文書への索引リンク。別 executable `strata-dsv41` にも同じ表記 `--pack` があるが、索引では `strata-engine-dsv41/root/--pack.md` として分離されている（`docs/cli/README.md:1353-1378`）。
