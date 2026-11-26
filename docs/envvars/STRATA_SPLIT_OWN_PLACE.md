# `STRATA_SPLIT_OWN_PLACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

複数 GPU の `--layer-split auto` が配置候補を評価するとき、各段の空き容量から自前 prompt buffer 用の reserve も差し引くかを切り替える。値が厳密に `reserve` の場合、探索時にも reserve を数える。それ以外では、`STRATA_SPLIT_OWN` によって自前 buffer を選んだ場合に限り、探索時の prompt buffer reserve を 0 として配置を評価する。実際の buffer 所有方式を選ぶ変数ではなく、reserve 分だけ探索時の容量と選ばれる split 境界が変わり得る。CUDA 実装は `engine/src/program/generate.cpp`、SYCL 実装は `engine/sycl/src/program/generate.cpp` にある（各実装の読み取りと容量計算: `engine/src/program/generate.cpp:6897-6922`、`engine/sycl/src/program/generate.cpp:3892-3913`）。

## 値と判定

両実装とも関数内 `static const bool` の初期化ラムダで `std::getenv` の結果を読み、値全体を `std::string(v) == "reserve"` で比較する。大文字小文字を区別し、空白除去・数値変換・部分一致はしない。

| 条件（backend） | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA (`engine/src/program/generate.cpp`) | `false`。自前 buffer が有効な auto 配置探索では buffer reserve を探索容量から除く | `reserve` のみ。探索容量から `split_pf_mib` を差し引く | 空文字、`0`、`1`、`Reserve`、`reserve ` など。unset と同じ扱い |
| SYCL (`engine/sycl/src/program/generate.cpp`) | `false`。自前 buffer が有効な auto 配置探索では buffer reserve を探索容量から除く | `reserve` のみ。探索容量から `split_pf_mib` を差し引く | 空文字、`0`、`1`、`Reserve`、`reserve ` など。unset と同じ扱い |

`reserve` 以外の設定値をエラーにしたり警告したりする処理はない。設定値は各 backend のプロセス内で、宣言に初めて到達したときに一度だけ評価される static 値であり、その後の環境変更は反映されない（同上）。

## 有効になる条件

- `--layer-split auto` による複数 GPU の配置探索が実行されること。手動の `--layer-split K[,K2..]` では候補探索をせず、この変数による切り替えは使われない。`--layer-split` は `--serve` が必要で、利用 GPU 数などの検証を通る必要がある（CUDA: `engine/src/program/generate.cpp:4785-4856`、SYCL: `engine/sycl/src/program/generate.cpp:2265-2334`）。
- `STRATA_SPLIT_OWN` が自前 prompt buffer を有効にしていること。コード上は `--no-prefill-borrow` が既に指定されておらず、`--split-skip-if-fits` も指定されず、`STRATA_SPLIT_OWN` が設定済みかつ先頭文字が `0` でない場合にその設定を判定する。`STRATA_SPLIT_OWN=auto` は GPU ごとの VRAM に対する 12% 条件を満たすと自前 buffer を選び、明示値は先頭文字 `1` で始まる場合に選ぶ（CUDA: `engine/src/program/generate.cpp:4916-4952`、SYCL: `engine/sycl/src/program/generate.cpp:2375-2419`）。この変数単独では自前 buffer を有効にしない。
- 自前 buffer が有効でも、`STRATA_SPLIT_OWN_PLACE` が `reserve` 以外なら、auto 探索時だけ `pf` を 0 にする。`reserve` なら `split_pf_mib` を探索容量に含める。`split_pf_mib` は `--prefill` chunk に基づく値（`160 + chunk * 680 / 1024` MiB に、該当時の split ring 分を加算）であり、prefill chunk が 0 以下なら基本分は 0（CUDA: `engine/src/program/generate.cpp:6821-6832,6907-6917`、SYCL: `engine/sycl/src/program/generate.cpp:3850-3860,3908-3912`）。
- `--vram-reserve-mib` および、後段 GPU 用の `--vram-reserve-later-mib` は別の reserve として探索容量に残る。これらを本変数が無効化することはない（CUDA: `engine/src/program/generate.cpp:6911-6922`、SYCL: `engine/sycl/src/program/generate.cpp:3908-3913`）。
- `--layer-split auto` の探索が一 GPU だけと判定され split を解除した場合や、容量不足などで探索に入らない場合は本変数の配置効果はない（CUDA: `engine/src/program/generate.cpp:4836-4847,6959-6971`、SYCL: `engine/sycl/src/program/generate.cpp:2313-2325,3921-3929`）。

## 実行時の詳細

CUDA は `place_with_reserve`、SYCL は同名の static 値を読み取る。auto 探索で各 GPU の `stage_room(..., search=true)` を呼ぶと、`split_own_auto` が真で、かつ本変数が `reserve` でない場合に `pf=0` とし、それ以外は `split_pf_mib` を `pf` にする。ここから VRAM reserve、段の window、drafter などを差し引いて探索用容量を作り、各候補の session 分なども差し引いて cache に残せる量を予測する。そのため `reserve` は prompt buffer 分だけ各候補の容量を小さくし、最良と判定される境界を変えることがある（CUDA: `engine/src/program/generate.cpp:6901-6922,6963-6971`、SYCL: `engine/sycl/src/program/generate.cpp:3896-3913,3921-3929`）。

この値は配置探索専用で、探索後に実行段の容量を計算する `stage_room` 呼び出しでは `search` が既定値 `false`。その場合はこの値や `split_own_auto` に関係なく `split_pf_mib` が計上される。従って、この変数は実行時の buffer 割当量を直接切り替えず、自前 buffer の選択自体にも影響しない（CUDA: `engine/src/program/generate.cpp:6901-6908,9893-9911`、SYCL: `engine/sycl/src/program/generate.cpp:3896-3908,5562-5573`）。子プロセスへの転送処理はこの名前の参照からは確認できない。

## ログと測定値

この変数の値だけを示すログや、無効値の警告はない。自動配置の経過として各 GPU の容量・性能を出力し、成功時には選んだ `K`、予測 decode 時間、cache が保持する expert 数などを stderr に出す（CUDA: `engine/src/program/generate.cpp:6971-6988,7510-7515`、SYCL: `engine/sycl/src/program/generate.cpp:3921-3945`）。有効な split が見つからない場合は `strata generate: --layer-split auto: no valid split for ...` を出して `return 2` するが、この変数に固有の失敗ではない（CUDA: `engine/src/program/generate.cpp:7501-7505`）。

## 根拠

- CUDA の読み取りと予約判定: `engine/src/program/generate.cpp:6897-6908`
- CUDA の自前 buffer 条件と reserve 算定: `engine/src/program/generate.cpp:4916-4952,6821-6832`
- CUDA の探索容量・配置候補への適用: `engine/src/program/generate.cpp:6911-6922,6963-6971`
- SYCL の読み取りと予約判定: `engine/sycl/src/program/generate.cpp:3892-3908`
- SYCL の自前 buffer 条件と reserve 算定: `engine/sycl/src/program/generate.cpp:2375-2419,3850-3860`
- SYCL の探索容量・配置候補への適用: `engine/sycl/src/program/generate.cpp:3908-3913,3921-3929`
