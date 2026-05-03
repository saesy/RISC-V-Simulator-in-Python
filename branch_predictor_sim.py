
MASK32 = 0xFFFFFFFF

# -------------------------
# 32-bit helpers
# -------------------------

def u32(x):
    return x & MASK32


def s32(x):
    x = x & MASK32
    if x & 0x80000000:
        return x - 0x100000000
    return x


def sign_extend(value, bits):
    mask = (1 << bits) - 1
    v = value & mask
    sign_bit = 1 << (bits - 1)
    if v & sign_bit:
        v = v - (1 << bits)
    return v


def get_bits(x, hi, lo):
    width = hi - lo + 1
    return (x >> lo) & ((1 << width) - 1)


# -------------------------
# Immediate generators
# -------------------------

def imm_i(instr):
    return sign_extend(get_bits(instr, 31, 20), 12)


def imm_s(instr):
    hi = get_bits(instr, 31, 25)
    lo = get_bits(instr, 11, 7)
    return sign_extend((hi << 5) | lo, 12)


def imm_b(instr):
    b12 = get_bits(instr, 31, 31)
    b11 = get_bits(instr, 7, 7)
    b10_5 = get_bits(instr, 30, 25)
    b4_1 = get_bits(instr, 11, 8)
    val = (b12 << 12) | (b11 << 11) | (b10_5 << 5) | (b4_1 << 1)
    return sign_extend(val, 13)


def imm_u(instr):
    return get_bits(instr, 31, 12) << 12


def imm_j(instr):
    j20 = get_bits(instr, 31, 31)
    j10_1 = get_bits(instr, 30, 21)
    j11 = get_bits(instr, 20, 20)
    j19_12 = get_bits(instr, 19, 12)
    val = (j20 << 20) | (j19_12 << 12) | (j11 << 11) | (j10_1 << 1)
    return sign_extend(val, 21)


# -------------------------
# Decode + Control
# -------------------------

def decode(instr):
    d = {}
    d["instr"] = u32(instr)
    d["opcode"] = get_bits(instr, 6, 0)
    d["rd"] = get_bits(instr, 11, 7)
    d["funct3"] = get_bits(instr, 14, 12)
    d["rs1"] = get_bits(instr, 19, 15)
    d["rs2"] = get_bits(instr, 24, 20)
    d["funct7"] = get_bits(instr, 31, 25)

    d["imm_I"] = imm_i(instr)
    d["imm_S"] = imm_s(instr)
    d["imm_B"] = imm_b(instr)
    d["imm_U"] = imm_u(instr)
    d["imm_J"] = imm_j(instr)
    return d


def main_control(d):
    op = d["opcode"]
    f3 = d["funct3"]

    c = {
        "RegWrite": 0,
        "MemRead": 0,
        "MemWrite": 0,
        "MemToReg": 0,
        "ALUSrc": 0,
        "Branch": 0,
        "Jump": 0,
        "JumpReg": 0,
        "ALUOp": "ADDR",
        "ImmSel": None,
        "BrType": None,
        "IsNOP": 0,
    }

    if d["instr"] == 0:
        c["IsNOP"] = 1
        return c

    if op == 0x33:  # R
        c["RegWrite"] = 1
        c["ALUSrc"] = 0
        c["ALUOp"] = "R"

    elif op == 0x13:  # I-ALU
        c["RegWrite"] = 1
        c["ALUSrc"] = 1
        c["ALUOp"] = "I"
        c["ImmSel"] = "I"

    elif op == 0x03:  # Load (lw)
        c["RegWrite"] = 1
        c["MemRead"] = 1
        c["MemToReg"] = 1
        c["ALUSrc"] = 1
        c["ALUOp"] = "ADDR"
        c["ImmSel"] = "I"

    elif op == 0x23:  # Store (sw)
        c["MemWrite"] = 1
        c["ALUSrc"] = 1
        c["ALUOp"] = "ADDR"
        c["ImmSel"] = "S"

    elif op == 0x63:  # Branch
        c["Branch"] = 1
        c["ALUSrc"] = 0
        c["ALUOp"] = "BR"
        c["ImmSel"] = "B"
        if f3 == 0b000:
            c["BrType"] = "beq"
        elif f3 == 0b001:
            c["BrType"] = "bne"
        elif f3 == 0b100:
            c["BrType"] = "blt"
        elif f3 == 0b101:
            c["BrType"] = "bge"
        elif f3 == 0b110:
            c["BrType"] = "bltu"
        elif f3 == 0b111:
            c["BrType"] = "bgeu"

    elif op == 0x6F:  # JAL
        c["Jump"] = 1
        c["RegWrite"] = 1
        c["ALUSrc"] = 1
        c["ALUOp"] = "ADDR"
        c["ImmSel"] = "J"

    elif op == 0x67:  # JALR
        c["Jump"] = 1
        c["JumpReg"] = 1
        c["RegWrite"] = 1
        c["ALUSrc"] = 1
        c["ALUOp"] = "ADDR"
        c["ImmSel"] = "I"

    return c


def select_imm(d, c):
    sel = c["ImmSel"]
    if sel == "I":
        return d["imm_I"]
    if sel == "S":
        return d["imm_S"]
    if sel == "B":
        return d["imm_B"]
    if sel == "U":
        return d["imm_U"]
    if sel == "J":
        return d["imm_J"]
    return 0


def alu_control(c, d):
    op = c["ALUOp"]
    f3 = d["funct3"]
    f7 = d["funct7"]

    if op == "ADDR":
        return "ADD"
    if op == "BR":
        return "SUB"

    if op == "R":
        if f3 == 0b000:
            return "SUB" if f7 == 0b0100000 else "ADD"
        if f3 == 0b111:
            return "AND"
        if f3 == 0b110:
            return "OR"
        if f3 == 0b100:
            return "XOR"
        if f3 == 0b001:
            return "SLL"
        if f3 == 0b101:
            return "SRA" if f7 == 0b0100000 else "SRL"
        if f3 == 0b010:
            return "SLT"
        if f3 == 0b011:
            return "SLTU"
        return "ADD"

    if op == "I":
        if f3 == 0b000:
            return "ADD"
        if f3 == 0b111:
            return "AND"
        if f3 == 0b110:
            return "OR"
        if f3 == 0b100:
            return "XOR"
        if f3 == 0b010:
            return "SLT"
        if f3 == 0b011:
            return "SLTU"
        if f3 == 0b001:
            return "SLL"
        if f3 == 0b101:
            return "SRA" if f7 == 0b0100000 else "SRL"
        return "ADD"

    return "ADD"


def alu_exec(alu_op, a, b):
    a = u32(a)
    b = u32(b)
    shamt = b & 0x1F

    if alu_op == "ADD":
        return u32(a + b)
    if alu_op == "SUB":
        return u32(a - b)
    if alu_op == "AND":
        return u32(a & b)
    if alu_op == "OR":
        return u32(a | b)
    if alu_op == "XOR":
        return u32(a ^ b)
    if alu_op == "SLL":
        return u32(a << shamt)
    if alu_op == "SRL":
        return u32(a >> shamt)
    if alu_op == "SRA":
        return u32(s32(a) >> shamt)
    if alu_op == "SLT":
        return 1 if s32(a) < s32(b) else 0
    if alu_op == "SLTU":
        return 1 if u32(a) < u32(b) else 0

    return u32(a + b)


def branch_taken(br_type, rs1_val, rs2_val):
    if br_type == "beq":
        return u32(rs1_val) == u32(rs2_val)
    if br_type == "bne":
        return u32(rs1_val) != u32(rs2_val)
    if br_type == "blt":
        return s32(rs1_val) < s32(rs2_val)
    if br_type == "bge":
        return s32(rs1_val) >= s32(rs2_val)
    if br_type == "bltu":
        return u32(rs1_val) < u32(rs2_val)
    if br_type == "bgeu":
        return u32(rs1_val) >= u32(rs2_val)
    return False


# -------------------------
# Data memory
# -------------------------

def dmem_load_word(dmem, addr):
    if addr % 4 != 0:
        raise ValueError("Unaligned lw at address 0x%08X" % addr)
    return u32(dmem.get(addr, 0))


def dmem_store_word(dmem, addr, value):
    if addr % 4 != 0:
        raise ValueError("Unaligned sw at address 0x%08X" % addr)
    dmem[addr] = u32(value)


# -------------------------
# Pipeline register helpers
# -------------------------

def make_if_id():
    return {"valid": 0, "pc": 0, "instr": 0}


def make_id_ex():
    return {
        "valid": 0,
        "pc": 0,
        "pc_plus4": 0,
        "d": None,
        "c": None,
        "imm": 0,
        "rs1": 0,
        "rs2": 0,
        "rd": 0,
        "rs1_val": 0,
        "rs2_val": 0,
        "alu_op": "ADD",
        "Branch": 0,
        "not_guessed_branch": 0,
    }


def make_ex_mem():
    return {
        "valid": 0,
        "pc_plus4": 0,
        "c": None,
        "d": None,
        "rd": 0,
        "alu_res": 0,
        "rs2_val_fwd": 0,
        "mem_addr": 0,
        "branch_taken": 0,
        "next_pc": 0,
        "wb_val_for_jumps": 0,
    }


def make_mem_wb():
    return {
        "valid": 0,
        "pc_plus4": 0,
        "c": None,
        "d": None,
        "rd": 0,
        "alu_res": 0,
        "mem_data": 0,
        "wb_val_for_jumps": 0,
    }


def is_nop_stage(stage):
    return stage is None or stage.get("valid", 0) == 0


# -------------------------
# Mnemonic (trace)
# -------------------------

def try_mnemonic(d):
    if d is None:
        return "NOP"
    op = d["opcode"]
    f3 = d["funct3"]
    f7 = d["funct7"]

    if d["instr"] == 0:
        return "NOP"

    if op == 0x33:
        if f3 == 0b000:
            return "sub" if f7 == 0b0100000 else "add"
        if f3 == 0b111:
            return "and"
        if f3 == 0b110:
            return "or"
        if f3 == 0b100:
            return "xor"
        if f3 == 0b001:
            return "sll"
        if f3 == 0b101:
            return "sra" if f7 == 0b0100000 else "srl"
        if f3 == 0b010:
            return "slt"
        if f3 == 0b011:
            return "sltu"
        return "r?"

    if op == 0x13:
        if f3 == 0b000:
            return "addi"
        if f3 == 0b111:
            return "andi"
        if f3 == 0b110:
            return "ori"
        if f3 == 0b100:
            return "xori"
        if f3 == 0b010:
            return "slti"
        if f3 == 0b011:
            return "sltiu"
        if f3 == 0b001:
            return "slli"
        if f3 == 0b101:
            return "srai" if f7 == 0b0100000 else "srli"
        return "i?"

    if op == 0x03 and f3 == 0b010:
        return "lw"
    if op == 0x23 and f3 == 0b010:
        return "sw"
    if op == 0x63:
        return {
            0b000: "beq",
            0b001: "bne",
            0b100: "blt",
            0b101: "bge",
            0b110: "bltu",
            0b111: "bgeu",
        }.get(f3, "b?")
    if op == 0x6F:
        return "jal"
    if op == 0x67:
        return "jalr"

    return "?"


# -------------------------
# Program loader + logs
# -------------------------

def load_imem_from_file(path):
    imem = {}
    pc = 0
    f = open(path, "r", encoding="utf-8")
    for line in f:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        if s.lower().startswith("0x"):
            s = s[2:]
        instr = int(s, 16) & MASK32
        imem[pc] = instr
        pc += 4
    f.close()
    return imem


def write_trace_log(lines, path):
    f = open(path, "w", encoding="utf-8")
    for ln in lines:
        f.write(ln + "\n")
    f.close()


def write_regs_log(regs, path):
    f = open(path, "w", encoding="utf-8")
    for i in range(32):
        f.write("x%-2d = 0x%08X (%d)\n" % (i, u32(regs[i]), s32(regs[i])))
    f.close()


def write_dmem_log(dmem, path):
    f = open(path, "w", encoding="utf-8")
    addrs = sorted(dmem.keys())
    for a in addrs:
        f.write("0x%08X : 0x%08X (%d)\n" % (u32(a), u32(dmem[a]), s32(dmem[a])))
    f.close()

def write_predictor_log(predictor_lines, path):
    f = open(path, "w", encoding="utf-8")
    for ln in predictor_lines:
        f.write(ln + "\n")
    f.close()


# -------------------------
# Hazard detection + forwarding
# -------------------------

def uses_rs1(d):
    if d is None:
        return False
    op = d["opcode"]
    if d["instr"] == 0:
        return False
    # Many instructions use rs1; U-type not in subset.
    if op in (0x33, 0x13, 0x03, 0x23, 0x63, 0x67):
        return True
    if op == 0x6F:  # jal uses no rs1
        return False
    return False


def uses_rs2(d):
    if d is None:
        return False
    op = d["opcode"]
    if d["instr"] == 0:
        return False
    # rs2 used in R-type, store, branch
    if op in (0x33, 0x23, 0x63):
        return True
    return False


def is_load_c(c):
    return c is not None and c.get("MemRead", 0) == 1 and c.get("MemToReg", 0) == 1


def will_write_c(c):
    return c is not None and c.get("RegWrite", 0) == 1


def forwarding_select(src_reg, ex_mem, mem_wb):
    """
    Return (use_forward, value):
      - Prefer EX/MEM if it will write rd and rd != 0 and rd == src_reg and rd value available now
      - Else MEM/WB similarly
    Notes:
      - For a load, EX/MEM does NOT have the loaded value yet; must use MEM/WB.
      - For jal/jalr, EX/MEM/MEM_WB provide wb_val_for_jumps (=pc+4).
    """
    if src_reg == 0:
        return 0, 0

    # EX/MEM forward (only if NOT a load)
    if ex_mem.get("valid", 0) == 1 and will_write_c(ex_mem.get("c")):
        rd = ex_mem.get("rd", 0)
        if rd != 0 and rd == src_reg:
            c = ex_mem.get("c")
            if is_load_c(c):
                pass
            else:
                if c.get("Jump", 0) == 1 and c.get("RegWrite", 0) == 1:
                    return 1, u32(ex_mem.get("wb_val_for_jumps", 0))
                return 1, u32(ex_mem.get("alu_res", 0))

    # MEM/WB forward (load data available here; also ALU and jump link)
    if mem_wb.get("valid", 0) == 1 and will_write_c(mem_wb.get("c")):
        rd = mem_wb.get("rd", 0)
        if rd != 0 and rd == src_reg:
            c = mem_wb.get("c")
            if c.get("Jump", 0) == 1 and c.get("RegWrite", 0) == 1:
                return 1, u32(mem_wb.get("wb_val_for_jumps", 0))
            if c.get("MemToReg", 0) == 1:
                return 1, u32(mem_wb.get("mem_data", 0))
            return 1, u32(mem_wb.get("alu_res", 0))

    return 0, 0


def load_use_hazard(if_id, id_ex):
    """
    Classic load-use hazard:
      If ID/EX is a load writing rd, and IF/ID instruction uses that rd as rs1 or rs2, stall.
    """
    if id_ex.get("valid", 0) == 0:
        return False
    c = id_ex.get("c")
    if not is_load_c(c):
        return False

    rd = id_ex.get("rd", 0)
    if rd == 0:
        return False

    if if_id.get("valid", 0) == 0:
        return False

    d2 = decode(if_id.get("instr", 0))
    # If instr is NOP (0), no hazard
    if d2["instr"] == 0:
        return False

    if uses_rs1(d2) and d2["rs1"] == rd:
        return True
    if uses_rs2(d2) and d2["rs2"] == rd:
        return True
    return False


# -------------------------
# Cycle trace
# -------------------------

def stage_str(name, stage_d, stage_c):
    if stage_d is None or stage_c is None:
        return name + ":NOP"
    return name + ":" + try_mnemonic(stage_d)


def trace_cycle(cycle, pc, stall, flush, if_id, id_ex, ex_mem, mem_wb, wb_info):
    parts = []
    parts.append("cycle=%d pc=0x%08X stall=%d flush=%d" % (cycle, u32(pc), 1 if stall else 0, 1 if flush else 0))

    d_if = decode(if_id["instr"]) if if_id.get("valid", 0) else None
    c_if = main_control(d_if) if d_if is not None else None
    if d_if is not None and d_if.get("instr", 0) == 0:
        c_if = main_control(d_if)

    parts.append("IF/ID=%s" % (try_mnemonic(d_if) if d_if is not None else "NOP"))
    parts.append("ID/EX=%s" % (try_mnemonic(id_ex.get("d")) if id_ex.get("valid", 0) else "NOP"))
    parts.append("EX/MEM=%s" % (try_mnemonic(ex_mem.get("d")) if ex_mem.get("valid", 0) else "NOP"))
    parts.append("MEM/WB=%s" % (try_mnemonic(mem_wb.get("d")) if mem_wb.get("valid", 0) else "NOP"))

    if wb_info:
        parts.append(wb_info)

    return " | ".join(parts)


# -------------------------
# Main pipeline simulation
# -------------------------

def main():
    imem = load_imem_from_file("hex_inst.txt")

    regs = [0] * 32
    dmem = {}

    #create branch predictor for full cpu use along mem and regs
    branch_predictor = 0b00
    increment_prediction = ""

    pc = 0
    cycle = 0
    max_cycles = 50_000_000  # big safety

    if_id = make_if_id()
    id_ex = make_id_ex()
    ex_mem = make_ex_mem()
    mem_wb = make_mem_wb()

    trace_lines = []
    predictor_lines = []
    branch_stats = {
        "branch_total": 0,
        "correct_predictions": 0,
    }

    # run until no more fetches and pipeline drains
    fetching_done = False

    while cycle < max_cycles:
        # -------------------------
        # WB stage (commit)
        # -------------------------
        wb_info = ""
        if mem_wb["valid"] == 1 and mem_wb["c"] is not None:
            c = mem_wb["c"]
            rd = mem_wb["rd"]
            wb_val = mem_wb["alu_res"]
            if c.get("MemToReg", 0) == 1:
                wb_val = mem_wb["mem_data"]
            if c.get("Jump", 0) == 1 and c.get("RegWrite", 0) == 1:
                wb_val = mem_wb["wb_val_for_jumps"]

            did_write = False
            if c.get("RegWrite", 0) == 1 and rd != 0:
                regs[rd] = u32(wb_val)
                did_write = True
            regs[0] = 0
            if did_write:
                wb_info = "WB: x%d<-0x%08X" % (rd, u32(wb_val))

        # -------------------------
        # MEM stage
        # -------------------------
        next_mem_wb = make_mem_wb()
        if ex_mem["valid"] == 1 and ex_mem["c"] is not None:
            c = ex_mem["c"]
            d = ex_mem["d"]
            next_mem_wb["valid"] = 1
            next_mem_wb["pc_plus4"] = ex_mem["pc_plus4"]
            next_mem_wb["c"] = c
            next_mem_wb["d"] = d
            next_mem_wb["rd"] = ex_mem["rd"]
            next_mem_wb["alu_res"] = ex_mem["alu_res"]
            next_mem_wb["wb_val_for_jumps"] = ex_mem["wb_val_for_jumps"]

            mem_data = 0
            addr = ex_mem["mem_addr"]

            if c.get("MemRead", 0) == 1:
                if d is not None and d.get("funct3", 0) == 0b010:
                    mem_data = dmem_load_word(dmem, addr)
            if c.get("MemWrite", 0) == 1:
                if d is not None and d.get("funct3", 0) == 0b010:
                    dmem_store_word(dmem, addr, ex_mem["rs2_val_fwd"])

            next_mem_wb["mem_data"] = u32(mem_data)

        # -------------------------
        # EX stage
        # -------------------------
        next_ex_mem = make_ex_mem()
        flush = False
        redirect_pc = 0

        if id_ex["valid"] == 1 and id_ex["c"] is not None:
            d = id_ex["d"]
            c = id_ex["c"]
            rs1 = id_ex["rs1"]
            rs2 = id_ex["rs2"]
            rd = id_ex["rd"]

            # forwarding for rs1/rs2 into EX
            a = id_ex["rs1_val"]
            b_reg = id_ex["rs2_val"]

            f1, v1 = forwarding_select(rs1, ex_mem, mem_wb)
            if f1:
                a = v1

            f2, v2 = forwarding_select(rs2, ex_mem, mem_wb)
            if f2:
                b_reg = v2

            imm = id_ex["imm"]
            alu_op = id_ex["alu_op"]

            alu_in2 = imm if c.get("ALUSrc", 0) == 1 else b_reg
            alu_res = alu_exec(alu_op, a, alu_in2)

            # store data must also be forwarded (rs2 path)
            store_data = b_reg

            # branch/jump resolve here (EX)
            next_pc = u32(id_ex["pc_plus4"])
            taken = False
            prediction_wrong = False

            if c.get("Branch", 0) == 1 and c.get("BrType") is not None:
                branch_stats["branch_total"]+=1
                taken = branch_taken(c.get("BrType"), a, b_reg)
                #update branch predictor with actual branching result
                # for 2-bit alg update at end of cycle
                if taken:
                    increment_prediction = "+"
                else:
                    increment_prediction = "-"
                #predictor already chose a path. If they do not match, change next_pc to id_ex["not_guessed_branch"]
                if (taken and (branch_predictor >> 1 == 0)) or (not taken and (branch_predictor >> 1 == 1)):
                    next_pc = id_ex["not_guessed_branch"]
                    prediction_wrong = True
                else:
                    next_pc = id_ex["pc_plus4"]
                    branch_stats["correct_predictions"]+=1
                
                #append to branch predictor log
                predictor_lines.append(f"mne: {try_mnemonic(id_ex["d"])} | Branch taken: {taken} | Correct: {not prediction_wrong} | Actual Next PC: {next_pc}")

            if c.get("Jump", 0) == 1:
                taken = True
                if c.get("JumpReg", 0) == 1:
                    next_pc = u32((a + imm) & 0xFFFFFFFE)
                else:
                    next_pc = u32(id_ex["pc"] + imm)

            # if taken control-flow, flush wrong-path (IF/ID) and bubble next ID/EX
            if prediction_wrong or (c.get("Jump",0) == 1):
                flush = True
                redirect_pc = next_pc

            next_ex_mem["valid"] = 1
            next_ex_mem["pc_plus4"] = id_ex["pc_plus4"]
            next_ex_mem["c"] = c
            next_ex_mem["d"] = d
            next_ex_mem["rd"] = rd
            next_ex_mem["alu_res"] = u32(alu_res)
            next_ex_mem["rs2_val_fwd"] = u32(store_data)
            next_ex_mem["mem_addr"] = u32(alu_res)
            next_ex_mem["branch_correct"] = 1 if taken else 0
            next_ex_mem["next_pc"] = u32(next_pc)
            next_ex_mem["wb_val_for_jumps"] = u32(id_ex["pc_plus4"])

        # -------------------------
        # ID stage (decode / reg read)
        # -------------------------
        stall = load_use_hazard(if_id, id_ex)

        next_id_ex = make_id_ex()

        if not stall:
            if if_id["valid"] == 1:
                instr = if_id["instr"]
                d = decode(instr)
                c = main_control(d)
                imm = select_imm(d, c)

                rs1 = d["rs1"]
                rs2 = d["rs2"]
                rd = d["rd"]

                next_id_ex["valid"] = 1
                next_id_ex["pc"] = if_id["pc"]
                next_id_ex["pc_plus4"] = u32(if_id["pc"] + 4)
                next_id_ex["d"] = d
                next_id_ex["c"] = c
                next_id_ex["imm"] = imm
                next_id_ex["rs1"] = rs1
                next_id_ex["rs2"] = rs2
                next_id_ex["rd"] = rd
                next_id_ex["rs1_val"] = u32(regs[rs1])
                next_id_ex["rs2_val"] = u32(regs[rs2])
                next_id_ex["alu_op"] = alu_control(c, d)

                #branch predictor if branch type
                if c["Branch"] == 1:
                    next_id_ex["Branch"] = 1
                    if (u32(branch_predictor) >> 1) == 1:
                        #predictor MSB is 1
                        predictor_lines.append(f"Cycle {cycle} ID Stage: Branch Predictor altered PC, assuming a branch will be needed.")
                        next_id_ex["pc_plus4"] = u32(if_id["pc"] + imm)
                        next_id_ex["not_guessed_branch"] = u32(if_id["pc"] + 4)
                    else: #MSB==0, guessing no branch, default to pc+4
                        next_id_ex["not_guessed_branch"] = u32(if_id["pc"] + imm)

        # flush after EX resolves taken branch/jump:
        # kill IF/ID and also kill what would enter ID/EX in same cycle update
        if flush:
            next_id_ex = make_id_ex()

        # On stall: insert bubble into ID/EX, keep IF/ID and PC same (handled in IF)
        if stall:
            next_id_ex = make_id_ex()

        # -------------------------
        # IF stage (fetch)
        # -------------------------
        next_if_id = make_if_id()

        # If flushing due to taken branch/jump, redirect PC and fetch from new PC next cycle
        # We model flush by updating PC now; IF/ID will be NOP for this cycle's update.
 
        
        if flush:
            pc = redirect_pc
            next_if_id = make_if_id()  # flushed
        else:
            if stall:
                # freeze IF/ID and PC (no fetch)
                next_if_id = if_id 
            else:        
                #branch predictor pc:
                if next_id_ex["Branch"] == 1:
                    pc = next_id_ex["pc_plus4"] #as redirect        

                # normal fetch
                instr = imem.get(u32(pc), None)
                if instr is None:
                    fetching_done = True
                    next_if_id["valid"] = 0
                else:
                    next_if_id["valid"] = 1
                    next_if_id["pc"] = u32(pc)
                    next_if_id["instr"] = u32(instr)
                pc = u32(pc + 4)

        # -------------------------
        # Trace for this cycle (before latching updates)
        # -------------------------
        trace_lines.append(trace_cycle(cycle, pc, stall, flush, next_if_id, next_id_ex, next_ex_mem, next_mem_wb, wb_info))

        # -------------------------
        # Latch updates
        # -------------------------
        mem_wb = next_mem_wb
        ex_mem = next_ex_mem
        id_ex = next_id_ex
        if_id = next_if_id

        #Branch predictor updates:
        if increment_prediction == "+": #check operator
            if branch_predictor != 0b11: #check if maximum
                branch_predictor = branch_predictor + 0b01
            predictor_lines.append(f"Cycle {cycle}: Branch was taken. 2-bit Predictor updated to {format(branch_predictor, '#003b')}.")
        elif increment_prediction == "-": #check operator
            if branch_predictor != 0b00: #check if minimum
                branch_predictor = branch_predictor - 0b01
            predictor_lines.append(f"Cycle {cycle}: Branch was not taken. 2-bit Predictor is {format(branch_predictor, '#003b')}. ")
        else:
            predictor_lines.append(f"Cycle {cycle}: No branch instruction this cycle")
        
        #reset for next branch instruction
        increment_prediction = ""
            

        # -------------------------
        # Halt condition: fetching done and pipeline drained
        # -------------------------
        if fetching_done:
            if if_id.get("valid", 0) == 0 and id_ex.get("valid", 0) == 0 and ex_mem.get("valid", 0) == 0 and mem_wb.get("valid", 0) == 0:
                break

        cycle += 1

    # Logs
    write_trace_log(trace_lines, "trace.log")
    write_regs_log(regs, "regs_final.log")
    write_dmem_log(dmem, "dmem_final.log")

    #prediction log
    accuracy_rate =  branch_stats["correct_predictions"] / branch_stats["branch_total"] * 100.0
    predictor_lines.append("==================================")
    predictor_lines.append(f"Total branches: {branch_stats["branch_total"]} | Correct Predictions: {branch_stats["correct_predictions"]}")
    predictor_lines.append("Accuracy rate: %.2f" % (accuracy_rate))
    write_predictor_log(predictor_lines, "predictor_trace.log")

    print("HALT")
    print("cycles =", cycle)
    print("wrote trace.log, regs_final.log, dmem_final.log")


if __name__ == "__main__":
    main()