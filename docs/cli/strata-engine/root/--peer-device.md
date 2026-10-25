# `--peer-device`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--peer-device N` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換される device ordinal。1以上で peer tier を有効化。既定値は `-1`（無効）。 |

## 役割

指定した CUDA device に、primary GPU が保持しない expert を置く第2の adaptive expert-cache tier を作ります。peer は割り当てられた expert の prompt rows と decode rows を計算し、結果を primary 側へ返します。索引上の scope は `src/program/generate.cpp` のネイティブ engine parser です。`strata-terminal` の同名 wrapper ではありません。

## 使い方

```sh
strata --pack /path/to/model.gguf --serve --expert-profile /path/to/profile.bin --expert-cache 8192 --peer-device 1
```

例の device ordinal は実行環境で peer として使う CUDA device に置き換えてください。peer tier には `--expert-profile` と有効な `--expert-cache` が必要です。通常の CLI parser では `--peer-device` に値が必要です。

## 値と既定値

- `Options::peer_device` の初期値は `-1` です。値が1以上の場合だけ起動時に peer tier を開き、`0` および負数では peer tier を開きません。
- 値は `std::atoi` で読み取られます。厳密な整数形式・範囲検証はこのオプションの parser にはありません。そのため、数値に変換できない文字列は `atoi` の結果 `0` となり、peer を有効にしません。複数回指定した場合は parser が順に代入し、最後の値が残ります。
- 値を省略すると parser の `next()` が `--peer-device needs a value` を stderr に出し、終了コード2で終了します。

## 実行時の動作

1. `peer_device >= 1` のとき、起動前の初期化で peer 用 mapped host buffer を使うフラグを有効化します。
2. expert profile を読み込んだ後、既定の `STRATA_PEER_HOT=0.45` と `STRATA_PEER_HOT_AT=8700`（profile の長さで上限）に従い、profile の上位 hot pair の一部を peer 側に回す順序へ並べ替えます。環境変数が設定されていればその値を使います。`STRATA_PEER_HOT` が0より大きく1より小さく、`HOT_AT` が正の値として解釈された場合に並べ替えます。
3. CUDA 実装は指定 ordinal が可視デバイスの範囲内か確認し、peer cache を開きます。primary が持たない ranked expert を、peer の空き VRAMから reserve 分を引いた予算内で、rank 順に格納します。空き領域がなく格納対象がない場合は失敗します。
4. peer tier は P2P capability を両方向で調べて有効化を試みます。P2P 経路が使えない場合は mapped host memory 経由になります。P2P が有効と報告された場合も小さなコピーを両方向で検査し、データが一致しなければ警告を stderr に出して P2P を無効化し host 経由へ切り替えます。`STRATA_PEER_NO_P2P` が非0なら P2P を使わない経路を選びます。
5. 正常に開くと stderr に peer GPU ordinal、格納 expert 数、VRAM 容量等を出力します。peer が有効な実行では prefill の fused ring を使わず、MMQ path と peer 用 buffer sizing を維持します。

## 適用条件と副作用

- ordinal は1以上でなければ有効になりません。実際の有効範囲は CUDA runtime が返す device count に依存し、指定値が `1 <= N < count` を満たさなければ拒否されます。
- `--expert-profile` が空、または `--expert-cache` が正数でなければ peer tier の初期化時に拒否されます。profile のロードに失敗した場合も別のエラー経路で終了します。
- prompt path は既定で chunk × top-k の半分の rows を peer に設定します。`--peer-prefill-rows 0` なら prompt rows を primary に残します。serve 中の peer adaptive round あたりの交換数は `--peer-adapt-swaps` を使い、未指定値 `-1` では primary 側の `--adapt-swaps` を使います。
- `--layer-split` または `--expert-cache-device1..3`（parser 上では remote cache の device slot）との併用は拒否され、stderr に理由を出して終了コード2になります。
- session save/restore は peer tier と併用できず、該当要求を `ERR` として拒否します。peer が有効だと `--pipeline-windows` の自動有効条件を満たさず、要求された pipeline windows も無効化されます。`--adapt-async` および適応処理の overlap も peer tier とは併用されません。
- CUDA `src/core/peer_experts.cpp` の計算経路は native expert pack のみをサポートし、非 native layout では `peer experts: only native packs are supported` の失敗になります。SYCL build は stub 実装であり、`--peer-device` を使うと「second-GPU expert tier is not ported to SYCL yet」として初期化が失敗します。
- peer GPU 上に CUDA stream/event、mapped host staging buffer、device input/output/scratch buffer と expert cache を確保し、profile に基づく expert blob を読み込みます。VRAM は `--peer-reserve-mib` の既定値600 MiB（実装上の最低 reserve は128 MiB）を残して使用可能量を計算します。

## 出力とエラー

- `--layer-split`／helper cache との競合は `strata generate: --peer-device cannot be combined with ...` を stderr に出し、終了コード2です。
- profile または expert cache がない場合は `strata generate: --peer-device needs --expert-profile and the expert cache` を stderr に出し、終了コード1です。
- ordinal が可視範囲外、peer GPU の初期化・buffer 確保・expert fill に失敗した場合は peer helper のエラー文字列を stderr に出して終了コード1です。空きがない場合の helper error は `peer experts: no room or no expert left for the peer` です。
- P2P の試験コピーが不一致の場合は警告を stderr に出しますが、peer 起動自体は host 経由で継続します。
- SYCL stub では初期化エラー `--peer-device: the second-GPU expert tier is not ported to SYCL yet` が返ります。

## 根拠

- 索引での scope と予定リンク: `docs/cli/README.md:1128-1135`。索引は `strata-engine` root を `src/program/generate.cpp` の engine 引数 parser と定義し、`--peer-device` を掲載しています。
- 既定値と option 定義: `src/program/generate.cpp:570-576`。
- help 表示上の用途と関連 option: `src/program/generate.cpp:1009-1016`。
- parser の値取得と未指定時の失敗: `src/program/generate.cpp:2416-2421,2743`。
- peer portable flag の設定: `src/program/generate.cpp:2923`。
- layer split / helper cache との競合: `src/program/generate.cpp:3369-3375`。
- profile hot pair の並べ替えと環境変数既定値: `src/program/generate.cpp:4414-4453`。
- peer tier 要件、初期化、起動時出力: `src/program/generate.cpp:6750-6766`。
- CUDA ordinal 検証、P2P 判定・試験コピー・fallback: `src/core/peer_experts.cpp:124-164`。
- VRAM reserve、slot 選択、空きなし／fill error: `src/core/peer_experts.cpp:191-241`。
- native pack 限定と prompt/decode row 計算経路: `src/core/peer_experts.cpp:291-313`。
- peer 時の prefill fused ring 抑止: `src/prefill/prefill.cpp:260-265,3626-3632`。
- peer prompt rows の初期設定と失敗時の primary-only fallback、serve 中の peer swap 数決定: `src/program/generate.cpp:8884-8890,10450-10458`。
- session file の拒否: `src/program/generate.cpp:12094-12099`。
- SYCL build の stub 収録と未対応エラー: `sycl/CMakeLists.txt:252-259`、`sycl/src/core/peer_experts.cpp:1-23`。
- 追加の利用者向け説明: `docs/SECOND_GPU.md:131-175`。この説明は上記 parser と実装を照合した補助資料として参照しました。

調査では source checkout のコードと既存文書を読み取り、CLI help 実行、build、GPU 実行、性能測定、テストは行っていません。Release artifact は確認していないため、各配布物での backend 対応状況は断定しません。
