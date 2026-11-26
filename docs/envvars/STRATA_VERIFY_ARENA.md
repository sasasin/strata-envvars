# `STRATA_VERIFY_ARENA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

アリーナへの expert データ読み込みが成功した後、読み込んだ `want` バイト全体の FNV-1a 64-bit checksum とサイズを stderr に出す診断用スイッチ。checksum は `fnv1a64(a->data(), want)` で計算され、seed は `1469598103934665603`、各 byte を XOR してから `1099511628211` を乗算する。値は表示だけに使われ、読み込み内容の照合、修復、生成結果の選択には使われない（`engine/src/core/expert_source.cpp:6853-6864`、`engine/sycl/src/core/expert_source.cpp:3504-3512`、`engine/src/core/pinned.cu:583-589`）。

実装は CUDA/HIP 系と SYCL 系それぞれの `strata::core::ArenaExpertSource::open` にある。通常のアリーナ読み込み経路で働く診断フックであり、環境値の内容は設定値として解釈されない。`terminal/data/settings-register.json:50933-50946` にも backend ごとの読み取り位置が登録されているが、実際の挙動の根拠は C++ 実装である。

## 値と判定

両 backend とも `std::getenv(...) != nullptr` のみを判定する。文字列変換、数値 parse、trim、大文字小文字判定はない。したがって未設定だけが無効で、空文字を含む設定済みの値はすべて有効。`0`、`false`、`true`、任意の文字列も区別されない（`engine/src/core/expert_source.cpp:6861-6864`、`engine/sycl/src/core/expert_source.cpp:3509-3512`）。

| 条件（backend） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP、SYCL の `ArenaExpertSource::open` が通常の読み込み完了まで進む | checksum ログなし | 空文字、`0`、`1`、`false`、`true`、その他の設定値 | なし（値が設定されている限り有効） |

## 有効になる条件

- 実行経路が `ArenaExpertSource::open` を呼ぶこと。CUDA/HIP の生成処理は `o.mmap_experts` 分岐を通らない場合に arena を開き（`engine/src/program/generate.cpp:8621-8622, 8745-8748, 8870-8872`）、SYCL は `--stream-experts` の直接 GGUF 読み込みでも `o.mmap_experts` のファイル tier でもない場合に arena を開く（`engine/sycl/src/program/generate.cpp:4711-4726, 4759-4776`）。
- `open` がアリーナの確保とデータ読み込みを完了し、`st.ok` かつ読み込み byte 数が `want` と一致すること。失敗または byte 数不一致なら、その前に `open` は失敗を返すため checksum は出ない（CUDA/HIP: `engine/src/core/expert_source.cpp:6848-6860`、SYCL: `engine/sycl/src/core/expert_source.cpp:3499-3509`）。
- `STRATA_ARENA_MMAP` で既存の padded `experts.bin` を直接 map する経路では、`open` が checksum 判定より前に成功を返すため、この変数が設定されていてもログは出ない（CUDA/HIP: `engine/src/core/expert_source.cpp:6490-6521`、SYCL: `engine/sycl/src/core/expert_source.cpp:3356-3385`）。
- OS、build macro、モデル、CLI 引数による値の parse 差はない。上記の backend 固有の実装がビルドされ、その通常のアリーナ読み込み経路に入ることが前提。

## 実行時の詳細

`ArenaExpertSource::open` が読み込みを終えた都度、成功判定の直後に現在の環境を読み、設定されていればアリーナの `want` バイトを走査して checksum を出力する。関数内 `static` への保存や cache はなく、プロセス起動時やリクエストごとではなく、アリーナを開くたびの読み取りである（`engine/src/core/expert_source.cpp:6445-6449, 6846-6864`、`engine/sycl/src/core/expert_source.cpp:3311-3315, 3496-3512`）。

CLI 引数や他の環境変数による値の上書き・優先順位はない。checksum の有無は読み込み済みデータ、arena の登録状態、以後の読み出し・生成処理を変更しない。失敗経路を成功扱いにしたり、checksum 不一致を検出して終了したりする処理もない。通常の CUDA/HIP 生成経路と SYCL の arena 経路では CLI/serve のどちらから呼ばれる場合も同じ条件でログを出すが、上記の mmap / streaming 経路は対象外。

## ログと測定値

有効で読み込みが成功した場合、stderr に次の形式で出る（値は実行時に計算される）。

```text
strata generate: expert arena checksum %016llx (%.2f GiB)
```

`%016llx` は FNV-1a 64-bit checksum、`%.2f GiB` は `want / 2^30`。変数未設定時、読み込み失敗時、既存 padded arena の直接 map 成功時にはこの行は出ない。`docs/DETAILS.md` にこの変数や checksum の測定結果の記載はなく、性能・正確性の測定値は確認できない。

## 根拠

- `engine/src/core/expert_source.cpp:6445-6457, 6846-6864` — CUDA/HIP の arena 開始、読み込み成功後の設定有無判定と出力。
- `engine/sycl/src/core/expert_source.cpp:3311-3323, 3496-3512` — SYCL の同じ判定と出力。
- `engine/src/core/pinned.cu:583-589` — CUDA/HIP 側 checksum 関数。
- `engine/include/strata/core/pinned.hpp:209` — checksum 関数宣言と既定 seed。
- `engine/src/program/generate.cpp:8621-8622, 8745-8748, 8870-8872` — CUDA/HIP 生成経路での arena 選択と呼び出し。
- `engine/sycl/src/program/generate.cpp:4711-4726, 4759-4777` — SYCL の streaming / file tier 分岐と arena 呼び出し。
- `engine/src/core/expert_source.cpp:6490-6521`、`engine/sycl/src/core/expert_source.cpp:3356-3385` — mmap 直返し経路。
- `terminal/data/settings-register.json:50933-50946` — 設定レジストリの backend と読み取り箇所の登録。
